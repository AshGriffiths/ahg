import argparse
import os

from ahg.git import (
    GitCommit,
    GitTree,
    cat_file,
    log_graphviz,
    ls_tree,
    object_find,
    object_hash,
    object_read,
    repo_create,
    repo_find,
    tree_checkout,
)


def cmd_add(args: argparse.Namespace) -> None:
    raise NotImplementedError()


def cmd_cat_file(args: argparse.Namespace) -> None:
    repo = repo_find()
    cat_file(repo, args.object, fmt=args.type.encode())


def cmd_check_ignore(args: argparse.Namespace) -> None:
    raise NotImplementedError()


def cmd_checkout(args: argparse.Namespace) -> None:
    repo = repo_find()

    obj = object_read(repo, object_find(repo, args.commit))
    if obj.fmt == b"commit":
        assert isinstance(obj, GitCommit)
        obj = object_read(repo, obj.kvlm[b"tree"].decode("ascii"))
        assert isinstance(obj, GitTree)

    if os.path.exists(args.path):
        if not os.path.isdir(args.path):
            raise Exception(f"Not not a directory {args.path}")
        if os.listdir(args.path):
            raise Exception(f"Not empty {args.path}")
    else:
        os.makedirs(args.path)

    assert isinstance(obj, GitTree)
    tree_checkout(repo, obj, os.path.realpath(args.path))


def cmd_commit(args: argparse.Namespace) -> None:
    raise NotImplementedError()


def cmd_hash_object(args: argparse.Namespace) -> None:
    if args.write:
        repo = repo_find()
    else:
        repo = None
    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)


def cmd_init(args: argparse.Namespace) -> None:
    repo_create(args.path)


def cmd_log(args: argparse.Namespace) -> None:
    repo = repo_find()

    print("digraph wyaglog{")
    print("  node[shape=rect]")
    log_graphviz(repo, object_find(repo, args.commit), set())
    print("}")


def cmd_ls_files(args: argparse.Namespace) -> None:
    raise NotImplementedError()


def cmd_ls_tree(args: argparse.Namespace) -> None:
    repo = repo_find()
    ls_tree(repo, args.tree, args.recursive)


def cmd_rev_parse(args: argparse.Namespace) -> None:
    raise NotImplementedError()


def cmd_rm(args: argparse.Namespace) -> None:
    raise NotImplementedError()


def cmd_show_ref(args: argparse.Namespace) -> None:
    raise NotImplementedError()


def cmd_status(args: argparse.Namespace) -> None:
    raise NotImplementedError()


def cmd_tag(args: argparse.Namespace) -> None:
    raise NotImplementedError()
