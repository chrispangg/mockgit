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
argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True


class GitRepository(object):
    # A basic data model for a git repository
    worktree = None  # Work directory path
    gitdir = None  # .git directory path
    conf = None  # Configurations

    def __init__(self, path, force=None):
        # Use init to check if git repo is valid. Use 'force' to bypass checks
        # valid repo will have .git
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception("Not a Git Repo %s" % path)

        # Read config file in .git/config using configparser
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")  # repo_file gets the path to config

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception("Unsupported repositoryformatversion %s" % vers)


def main(argv=sys.argv[1:]):
    # call functions based on the returned string from the subparser
    args = argparser.parse_args(argv)

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


def repo_path(repo, *path):
    # Compute path under repo's gitdir
    return os.path.join(repo.gitdir, *path)


def repo_file(repo, *path, mkdir=False):
    # Same as repo_path but creates the path to file using repo_dir if absent.
    # For example, repo_file(r, \"refs\", \"remotes\", \"origin\", \"HEAD\") will create .git/refs/remotes/origin.

    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)


def repo_dir(repo, *path, mkdir=False):
    # Make directory to the path if absent and if mkdir

    path = repo_path(repo, *path)

    if os.path.exists(path):
        if os.path.isdir(path):
            return path
        else:
            raise Exception("Not a directory %s" % path)

    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None


def repo_create(path):
    # Create a new repository at path

    repo = GitRepository(path, True)

    # An existing path for our repo should be a directory and an empty directory
    # Create a new directory path if doesn't exist
    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception("%s is not a directory!" % path)
        if os.path.exists(repo.gitdir) and os.path.isdir(repo.gitdir):
            raise Exception("%s is already a pangit repo (contains a .git)!" % path)
    else:
        os.makedirs(repo.gitdir)

    # .git/branches/ : the branch store
    assert repo_dir(repo, "branches", mkdir=True)

    # .git/objects/ : the object store
    assert repo_dir(repo, "objects", mkdir=True)

    # .git/refs/ : the reference store, contains two subdirectories, heads and tags
    assert repo_dir(repo, "refs", "tags", mkdir=True)
    assert repo_dir(repo, "refs", "heads", mkdir=True)

    # git/description : the repository’s description file
    with open(repo_file(repo, "description"), "w") as f:
        f.write(
            "Unnamed repository; edit this file 'description' to name the repository.\n"
        )

    # git/HEAD: a reference to the current HEAD
    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/main\n")

    # git/config: the repository’s configuration file
    with open(repo_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)

    return repo


def repo_default_config():
    # method for generating the config file

    ret = configparser.ConfigParser()
    ret.add_section("core")

    # repositoryformatversion=0: the version of the gitdir format. 0 means the initial format, 1 the same with extensions.
    ret.set("core", "repositoryformatversion", "0")

    # filemode=false: disable tracking of file mode changes in the work tree
    ret.set("core", "filemode", "false")

    # bare=false: to indicate this repo has a worktree
    ret.set("core", "bare", "false")

    return ret


# an argparse subparser to handle the init command’s argument
argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repository.")

# add an argument "." to create default path from the current directory
argsp.add_argument(
    "path",
    metavar="directory",
    nargs="?",
    default=".",
    help="Where to create the repository.",
)


def cmd_init(args):
    repo_create(args.path)


def repo_find(path=".", required=True):
    # repo_find looks for a repo (.git folder), starting at current directory and recursing back until "/"
    path = os.path.realpath(path)

    # if .git directory exist return GitRepository object
    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path)

    # If we haven't returned, recurse in parent, if w
    parent = os.path.realpath(os.path.join(path, ".."))

    # parent will be equal path when it's at root
    if parent == path:
        if required:
            raise Exception("No git directory.")
        else:
            return None

    return repo_find(parent, required)
