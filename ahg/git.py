import collections
import configparser
import hashlib
import os
import sys
import zlib

from io import BufferedReader


class GitRepository(object):
    """A git repository."""

    def __init__(self, path: str, force: bool = False) -> None:
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception(f"Not a Git repository {path}")

        # Read configuration file in .git/config
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception(f"Unsupported repositoryformatversion {vers}")


class GitTreeLeaf(object):
    def __init__(self, mode: bytes, path: str, sha: str) -> None:
        self.mode = mode
        self.path = path
        self.sha = sha


class GitObject(object):
    fmt = b""

    def __init__(self, data: bytes | None = None) -> None:
        if data:
            self.deserialize(data)
        else:
            super().__init__()

    def serialize(self) -> bytes:
        """This function MUST be implemented by subclasses.

        It must read the object's contents from self.data, a byte string, and do
        whatever it takes to convert it into a meaningful representation. What
        exactly that means depends on each subclass."""
        raise NotImplementedError()

    def deserialize(self, data: bytes) -> None:
        raise NotImplementedError()


class GitBlob(GitObject):
    fmt = b"blob"

    def deserialize(self, data):
        self.blobdata = data

    def serialize(self) -> bytes:
        return self.blobdata

    def __init__(self, data: bytes | None = None) -> None:
        super().__init__(data)


class GitCommit(GitObject):
    fmt = b"commit"

    def deserialize(self, data):
        self.kvlm = kvlm_parse(data)

    def serialize(self) -> bytes:
        return kvlm_serialize(self.kvlm)

    def __init__(self, data: bytes | None = None) -> None:
        super().__init__(data)
        self.kvlm = dict()


class GitTree(GitObject):
    fmt = b"tree"

    def deserialize(self, data) -> None:
        self.items = tree_parse(data)

    def serialize(self) -> bytes:
        return tree_serialize(self)

    def __init__(self, data: bytes | None = None) -> None:
        super().__init__(data)
        self.items = list()


class GitTag(GitCommit):
    fmt = b"tag"


def repo_path(repo, *path: str) -> str:
    """Compute path under repo's gitdir."""
    return os.path.join(repo.gitdir, *path)


def repo_dir(repo: GitRepository, *path: str, mkdir: bool = False) -> str | None:
    """Same as repo_path, but mkdir *path if absent if mkdir."""

    full_path = repo_path(repo, *path)

    if os.path.exists(full_path):
        if os.path.isdir(full_path):
            return full_path
        else:
            raise Exception(f"Not a directory {full_path}")

    if mkdir:
        os.makedirs(full_path)
        return full_path
    else:
        return None


def repo_file(repo: GitRepository, *path: str, mkdir: bool = False):
    """Same as repo_path, but create dirname(*path) if absent.  For example,
    repo_file(r, \"refs\", \"remotes\", \"origin\", \"HEAD\")
    will create .git/refs/remotes/origin.
    """
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)


def repo_default_config() -> configparser.ConfigParser:
    ret = configparser.ConfigParser()

    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")

    return ret


def repo_create(path: str) -> GitRepository:
    """Create a new repository at path."""

    repo = GitRepository(path, True)

    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception(f"{path} is not a directory!")
        if os.path.exists(repo.gitdir) and os.listdir(repo.gitdir):
            raise Exception(f"{path} is not empty!")
    else:
        os.makedirs(repo.worktree)

    assert repo_dir(repo, "branches", mkdir=True)
    assert repo_dir(repo, "objects", mkdir=True)
    assert repo_dir(repo, "refs", "tags", mkdir=True)
    assert repo_dir(repo, "refs", "heads", mkdir=True)

    with open(repo_file(repo, "description"), "w") as f:
        f.write(
            "Unnamed repository; edit this file 'description' to name the repository.\n"
        )

    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/main\n")

    with open(repo_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)

    return repo


def repo_find(path: str = ".", required: bool = True) -> GitRepository:
    path = os.path.realpath(path)

    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path)

    parent = os.path.realpath(os.path.join(path, ".."))

    if parent == path:
        raise Exception("No git directory.")

    return repo_find(parent, required)


def object_read(repo: GitRepository, sha: str) -> GitObject:
    """Read object sha from Git repository repo. Return a GitObject whose exact type
    depends on the object."""

    path = repo_file(repo, "objects", sha[0:2], sha[2:])

    if not os.path.isfile(path):
        raise Exception(f"Object {sha} not found!")

    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())
        x = raw.find(b" ")
        fmt = raw[0:x]

        y = raw.find(b"\x00", x)
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw) - y - 1:
            raise Exception(f"Malformed object {sha}: bad length")

        match fmt:
            case b"commit":
                c: type[GitObject] = GitCommit
            case b"tree":
                c = GitTree
            case b"tag":
                c = GitTag
            case b"blob":
                c = GitBlob
            case _:
                raise Exception(f"Unknown type {fmt.decode('ascii')} for object {sha}")

        return c(raw[y + 1 :])


def object_write(obj: GitObject, repo: GitRepository | None = None) -> str:
    data = obj.serialize()
    result = obj.fmt + b" " + str(len(data)).encode() + b"\x00" + data
    sha = hashlib.sha1(result).hexdigest()

    if repo:
        path = repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(zlib.compress(result))

    return sha


def object_find(repo: GitRepository, name: str, fmt: bytes | None = None) -> str:
    return name


def object_hash(fd: BufferedReader, fmt: str, repo: GitRepository | None = None) -> str:
    """Hash object, writing it to repo if provided."""
    data = fd.read()

    match fmt:
        case b"commit":
            obj = GitCommit(data)
        case b"tree":
            obj = GitTree(data)
        case b"tag":
            obj = GitTag(data)
        case b"blob":
            obj = GitBlob(data)
        case _:
            raise Exception(f"Unknown type {fmt}!")

    return object_write(obj, repo)


def cat_file(repo: GitRepository, obj: str, fmt: bytes | None = None) -> None:
    gobj: GitObject = object_read(repo, object_find(repo, obj, fmt=fmt))

    sys.stdout.buffer.write(gobj.serialize())


def kvlm_parse(
    raw: bytes, start: int = 0, dct: collections.OrderedDict | None = None
) -> collections.OrderedDict:
    if not dct:
        dct = collections.OrderedDict()

    spc = raw.find(b" ", start)
    nl = raw.find(b"\n", start)

    # Base case, found blank line, must be commit message next
    if (spc < 0) or (nl < spc):
        assert nl == start
        dct[None] = raw[start + 1 :]
        return dct

    # Recurse case, k-v pair
    key = raw[start:spc]
    # check if next line starts with space and as such is a continuation
    end = start
    while True:
        end = raw.find(b"\n", end + 1)
        if raw[end + 1] != ord(" "):
            break
    # Get the value and drop any continuation spaces
    value = raw[spc + 1 : end].replace(b"\n ", b"\n")

    if key in dct:
        if dct[key] is list:
            dct[key].append(value)
        else:
            dct[key] = [dct[key], value]
    else:
        dct[key] = value

    return kvlm_parse(raw, start=end + 1, dct=dct)


def kvlm_serialize(kvlm: collections.OrderedDict) -> bytes:
    ret = b""

    for k in kvlm.keys():
        if not k:
            continue
        val = kvlm[k]
        if val is not list:
            val = [val]

        for v in val:
            ret += k + b" " + (v.replace(b"\n", b"\n ")) + b"\n"

    ret += b"\n" + kvlm[None] + b"\n"

    return ret


def log_graphviz(repo: GitRepository, sha: str, seen: set) -> None:
    # Stop case, seen this before
    if sha in seen:
        return
    seen.add(sha)

    commit = object_read(repo, sha)
    assert isinstance(commit, GitCommit)

    short_hash = sha[0:8]
    message: str = commit.kvlm[None].decode("utf8").strip()
    message = message.replace("\\", "\\\\")
    message = message.replace('"', '\\"')

    if "\n" in message:
        message = message[: message.index("\n")]

    print(f'  c_{sha} [label="{short_hash}: {message}"]')

    if b"parent" not in commit.kvlm.keys():
        # Base case, initial commit
        return

    parents = commit.kvlm[b"parent"]

    if parents is not list:
        parents = [parents]

    # Recursive case
    for p in parents:
        p = p.decode("ascii")
        print(f"  c_{sha} -> c_{p}")
        log_graphviz(repo, p, seen)


def tree_parse_one(raw: bytes, start: int = 0) -> tuple[int, GitTreeLeaf]:
    x = raw.find(b" ", start)
    assert x - start == 5 or x - start == 6

    mode = raw[start:x]
    if len(mode) == 5:
        mode = b" " + mode

    y = raw.find(b"\x00", x)
    path = raw[x + 1 : y]

    sha = format(int.from_bytes(raw[y + 1 : y + 21], "big"), "040x")
    return y + 21, GitTreeLeaf(mode, path.decode("utf8"), sha)


def tree_parse(raw: bytes) -> list[GitTreeLeaf]:
    pos = 0
    max = len(raw)
    ret = list()
    while pos < max:
        pos, data = tree_parse_one(raw, pos)
        ret.append(data)
    return ret


def tree_leaf_sort_key(leaf: GitTreeLeaf) -> str:
    if leaf.mode.startswith(b"10"):
        return leaf.path
    else:
        return leaf.path + "/"


def tree_serialize(obj: GitTree) -> bytes:
    obj.items.sort(key=tree_leaf_sort_key)
    ret = b""
    for i in obj.items:
        ret += i.mode
        ret += b" "
        ret += i.path.encode("utf8")
        ret += b"\x00"
        sha = int(i.sha, 16)
        ret += sha.to_bytes(20, byteorder="big")
    return ret


def ls_tree(repo: GitRepository, ref: str, recursive: bool = False, prefix: str = ""):
    sha = object_find(repo, ref, fmt=b"tree")
    obj = object_read(repo, sha)
    assert isinstance(obj, GitTree)
    for item in obj.items:
        if len(item.mode) == 5:
            mode = item.mode[0:1]
        else:
            mode = item.mode[0:2]

        match mode:
            case b"04":
                type = "tree"  # another directory
            case b"10":
                type = "blob"  # file
            case b"12":
                type = "blob"  # symlink as blob
            case b"16":
                type = "commit"  # submodule
            case _:
                raise Exception(f"Weird tree lead mode {item.mode.decode('ascii')}")

        if not (recursive and type == "tree"):  # leaf node
            print(
                f"{'0' * (6 - len(item.mode)) + item.mode.decode('ascii')}"
                f"{type} {item.sha}\t{os.path.join(prefix, item.path)}"
            )
        else:  # recurse
            ls_tree(repo, item.sha, recursive, os.path.join(prefix, item.path))


def tree_checkout(repo: GitRepository, tree: GitTree, path: str) -> None:
    for item in tree.items:
        obj = object_read(repo, item.sha)
        dest = os.path.join(path, item.path)

        if isinstance(obj, GitTree):
            os.mkdir(dest)
            tree_checkout(repo, obj, dest)
        elif isinstance(obj, GitBlob):
            # TODO: Handle symlinks (Mode 12)
            with open(dest, "wb") as f:
                f.write(obj.blobdata)
