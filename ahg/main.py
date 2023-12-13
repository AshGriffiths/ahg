import argparse
import sys

import ahg.commands as commands

argparser = argparse.ArgumentParser(description="An attempt at implementing git.")

argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
# init
argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repository.")
argsp.add_argument(
    "path",
    metavar="directory",
    nargs="?",
    default=".",
    help="Where to create the repository.",
)
# cat-file
argsp = argsubparsers.add_parser(
    "cat-file", help="Provide content of repository objects"
)
argsp.add_argument(
    "type",
    metavar="type",
    choices=["blob", "commit", "tag", "tree"],
    help="Specify the type",
)
argsp.add_argument("object", metavar="object", help="The object to display")
# hash-object
argsp = argsubparsers.add_parser(
    "hash-object", help="Compute object ID and optionally creates a blob from a file"
)
argsp.add_argument(
    "-t",
    metavar="type",
    dest="type",
    choices=["blob", "commit", "tag", "tree"],
    default="blob",
    help="Specify the type",
)
argsp.add_argument(
    "-w",
    dest="write",
    action="store_true",
    help="Actually write the object into the database",
)
argsp.add_argument("path", help="Read object from <file>")
# log
argsp = argsubparsers.add_parser("log", help="Display history of a given commit.")
argsp.add_argument("commit", default="HEAD", nargs="?", help="Commit to start at.")
# ls-tree
argsp = argsubparsers.add_parser("ls-tree", help="Pretty-print a tree object.")
argsp.add_argument(
    "-r", dest="recursive", action="store_true", help="Recurse into sub-trees"
)
argsp.add_argument("tree", help="A tree-ish object.")
# checkout (basic version that only checks out to an empty directory to avoid potentially wrecking files not under gits control)
argsp = argsubparsers.add_parser(
    "checkout", help="Checkout a commit inside of a directory."
)
argsp.add_argument("commit", help="THe commit or tree to checkout.")
argsp.add_argument("path", help="The EMPTY directory to checkout on.")
argsubparsers.required = True


def main(argv: list[str] = sys.argv[1:]) -> None:
    args: argparse.Namespace = argparser.parse_args(argv)
    match args.command:
        case "add":
            commands.cmd_add(args)
        case "cat-file":
            commands.cmd_cat_file(args)
        case "check-ignore":
            commands.cmd_check_ignore(args)
        case "checkout":
            commands.cmd_checkout(args)
        case "commit":
            commands.cmd_commit(args)
        case "hash-object":
            commands.cmd_hash_object(args)
        case "init":
            commands.cmd_init(args)
        case "log":
            commands.cmd_log(args)
        case "ls-files":
            commands.cmd_ls_files(args)
        case "ls-tree":
            commands.cmd_ls_tree(args)
        case "rev-parse":
            commands.cmd_rev_parse(args)
        case "rm":
            commands.cmd_rm(args)
        case "show-ref":
            commands.cmd_show_ref(args)
        case "status":
            commands.cmd_status(args)
        case "tag":
            commands.cmd_tag(args)
        case _:
            print("Bad command.")
