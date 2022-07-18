import argparse, collections, configparser, hashlib, os, re, sys, zlib

# argparse - for parsing command-line arguments
# collections - for OrderedDict, which is not included in the base lib
# configparser - for reading and writing INI files
# hashlib - for SHA-1 which git uses heavily
# os - for accessing and manipulating the filesystem
# re - for regex
# sys - for accessing command line arg
# zlib - for compressing objects which git does as well

argparser = argparse.ArgumentParser(description="Content tracker")
# argsubparsers for subcommands such as git add or git checkout
argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True


def main(argv=sys.argv[1:]):
    # call functions based on the returned string from the subparser
    args = argsubparsers.parse_args(argv)

    if args.command == "add":
        cmd_add(args)
    elif args.command == "cat-file":
        cmd_cat_file(args)
    elif args.command == "checkout":
        cmd_checkout(args)
    elif args.command == "commit":
        cmd_commit(args)
    elif args.command == "hash-object":
        cmd_hash_object(args)
    elif args.command == "init":
        cmd_init(args)
    elif args.command == "log":
        cmd_log(args)
    elif args.command == "ls-tree":
        cmd_ls_tree(args)
    elif args.command == "merge":
        cmd_merge(args)
    elif args.command == "rebase":
        cmd_rebase(args)
    elif args.command == "rev-parse":
        cmd_rev_parse(args)
    elif args.command == "rm":
        cmd_rm(args)
    elif args.command == "show-ref":
        cmd_show_ref(args)
    elif args.command == "tag":
        cmd_tag(args)

