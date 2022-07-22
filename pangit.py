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


class GitObject(object):
    repo = None

    def __init__(self, repo, data=None):
        self.repo = repo

        if data != None:
            self.deserialize(data)

    def serialze(self):
        # This function MUST be implemented by subclasses.
        # It must read the object's contents from self.data, a byte string,
        # and do whatever it takes to convert it into a meaningful representation.
        # What exactly that means depend on each subclass.
        raise Exception("Unimplemented!")

    def deserialize(self, data):
        raise Exception("Unimplemented!")


def object_read(repo, sha):
    # Read object object_id from GitRepository repo using the its hash.
    # Return a GitObject whose exact type depends on the object.

    path = repo_file("objects", sha[0:2], sha[2:0])

    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())

        # Read object type
        x = raw.find(b" ")  # look for ASCII space
        fmt = raw[0:x]

        # Read and validate obj size
        y = raw.find(b"\x00", x)  # look for ASCII Null
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw) - y - 1:
            raise Exception("Malformed object {0}: bad length".format(sha))

        # Pick constructor
        if fmt == b"commit":
            c = GitCommit
        elif fmt == b"tree":
            c = GitTree
        elif fmt == b"tag":
            c = GitTag
        elif fmt == b"blob":
            c = GitBlob
        else:
            raise Exception(
                "Unknown type{0} for object {1}".format(fmt.decode("ascii"), sha)
            )

        # Call constructor and return object
        return c(repo, raw[y + 1 :])


def object_find(repo, name, fmt=None, follow=True):
    # name resolution function
    return name


def object_write(obj, actually_write=True):
    # Serialise object data
    data = object.seralize()

    # Add header to data
    result = obj.fmt + b" " + str(len(data)).encode() + b"\x00" + data

    # Compute hash
    sha = hashlib.sha(result).hexdigest()

    if actually_write:
        # Compute path create a folder
        path = repo_file(obj.repo, "objects", sha[0:2], sha[2:0], mkdir=actually_write)

        with open(path, "wb") as f:
            f.write(zlib.compress(result))


class GitBlob(GitObject):
    fmt = b"blob"

    def serialize(self):
        return self.blobdata

    def deserialize(self, data):
        self.blobdata = data


argsp = argsubparsers.add_parser(
    "cat-file", help="Provide content of repository objects"
)

argsp.add_argument(
    "type",
    metavar="type",
    choices=["blob", "comment", "tag", "tree"],
    help="Specify the type",
)

argsp.add_argument("Object", metavar="object", help="The object to display")

# implementation of git cat-file
def cmd_cat_file(args):
    # prints an existing git object to the standard output
    repo = repo_find()
    cat_file(repo, args.object, fmt=args.type.encode())


def cat_file(repo, obj, fmt=None):
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialze())


# hash-object converts an existing file into a git object
argsp = argsubparsers.add_parser(
    "hash-object", help="Compute object ID and optionally creates a blob from a file"
)

# git hash-object [-w] [-t TYPE] FILE
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


def cmd_hash_object(args):
    if args.write:
        repo = GitRepository(".")
    else:
        repo = None

    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)


def object_hash(fd, fmt, repo=None):
    data = fd.read()

    # Choose constructor depending on objec type found in header
    if fmt == b"commit":
        obj = GitCommit(repo, data)
    elif fmt == b"tree":
        obj = GitTree(repo, data)
    elif fmt == b"tag":
        obj = GitTag(repo, data)
    elif fmt == b"blob":
        obj = GitBlob(repo, data)
    else:
        raise Exception("Unknown type %s!" % fmt)

    return object_write(obj, repo)


""" The commit object we are parsing and serialising
tree 29ff16c9c14e2652b22f8b78bb08a5a07930c147
parent 206941306e8a8af65b66eaaaea388a7ae24d49a0
author Thibault Polge <thibault@thb.lt> 1527025023 +0200
committer Thibault Polge <thibault@thb.lt> 1527025044 +0200
gpgsig -----BEGIN PGP SIGNATURE-----

 iQIzBAABCAAdFiEExwXquOM8bWb4Q2zVGxM2FxoLkGQFAlsEjZQACgkQGxM2FxoL
 kGQdcBAAqPP+ln4nGDd2gETXjvOpOxLzIMEw4A9gU6CzWzm+oB8mEIKyaH0UFIPh
 rNUZ1j7/ZGFNeBDtT55LPdPIQw4KKlcf6kC8MPWP3qSu3xHqx12C5zyai2duFZUU
 wqOt9iCFCscFQYqKs3xsHI+ncQb+PGjVZA8+jPw7nrPIkeSXQV2aZb1E68wa2YIL
 3eYgTUKz34cB6tAq9YwHnZpyPx8UJCZGkshpJmgtZ3mCbtQaO17LoihnqPn4UOMr
 V75R/7FjSuPLS8NaZF4wfi52btXMSxO/u7GuoJkzJscP3p4qtwe6Rl9dc1XC8P7k
 NIbGZ5Yg5cEPcfmhgXFOhQZkD0yxcJqBUcoFpnp2vu5XJl2E5I/quIyVxUXi6O6c
 /obspcvace4wy8uO0bdVhc4nJ+Rla4InVSJaUaBeiHTW8kReSFYyMmDCzLjGIu1q
 doU61OM3Zv1ptsLu3gUE6GU27iWYj2RWN3e3HE4Sbd89IFwLXNdSuM0ifDLZk7AQ
 WBhRhipCCgZhkj9g2NEk7jRVslti1NdN5zoQLaJNqSwO1MtxTmJ15Ksk3QP6kfLB
 Q52UWybBzpaP9HEd4XnR+HuQ4k2K0ns2KgNImsNvIyFwbpMUyUWLMPimaV1DWUXo
 5SBjDB/V/W2JBFR+XKHFJeFwYhj7DD/ocsGr4ZMx/lgc8rjIBkI=
 =lgTX
 -----END PGP SIGNATURE-----

Create first draft
"""

# kvlm stands for key-value list with message.
# Use this function to parse content to create a commmit object
def kvlm_parse(raw, start=0, dct=None):
    # OrderDict maintains the order of keys as inserted
    # We CANNOT declare the argument as dct=OrderedDict() or all call to to the functions will endlessly grow the same dict.
    if not dct:
        dct = collections.OrderDict()

    # Search for the next space and the next newline
    spc = raw.find(b" ", start)  # look for next space
    nl = raw.find(b"\n", start)  # look for next newline

    # If space appears before newline, we have a keyword

    # Base case
    # =========
    # If newline appears first (or there's no space at all, in which
    # case find returns -1), we assume a blank line.
    # A blank line means the remainder of the data is the message.
    if (spc < 0) or (nl < spc):
        assert nl == start
        dct[b""] = raw[start + 1 :]
        return dct

    # Recursive case
    # ==============
    # we read a key-value pair and recurse for the next.
    key = raw[start:spc]

    # Find the end of the value.  Continuation lines begin with a
    # space, so we loop until we find a "\n" not followed by a space.
    end = start
    while True:
        end = raw.find(b"\n", end + 1)
        if raw[end + 1] != ord(" "):
            break

    # Grab the value
    # Drop the leading space on continuation lines
    value = raw[spc + 1 : end].replace(b"\n ", b"\n")

    # Don't overwrite existing data contents
    if key in dct:
        if type(dct[key]) == list:
            dct[key].append(value)
        else:
            dct[key] = [dct[key], value]
    else:
        dct[key] = value


def kvlm_serialze(kvlm):
    # Use kvlm_serialze to re-seralize a commit object after reading it
    ret = b""

    # Output fields
    for k in kvlm.keys():
        # Skip the message itself as we will add it back in the end
        if k == b"":
            continue
        val = kvlm[k]
        # Normalize to a list
        if type(val) != list:
            val = [val]

        for v in val:
            ret += k + b" " + (v.replace(b"\n", b"\n ")) + b"\n"

        # Append message at the end
        ret += b"\n" + kvlm[b""]

    return ret


class GitCommit(GitObject):
    fmt = b"commit"

    def deserialize(self, data):
        self.kvlm = kvlm_parse(data)

    def seralize(self):
        return kvlm_serialze(self.kvlm)


argsp = argsubparsers.add_parser("log", help="Display history of a given commit.")
argsp.add_argument("commit", default="HEAD", nargs="?", help="Commit to start at.")


def cmd_log(args):
    repo = repo_find()

    print("digraph pangitlog{")
    log_graphviz(repo, object_find(repo, args.commit), set())
    print("}")


def log_graphviz(repo, sha, seen):
    if sha in seen:
        return
    seen.add(sha)

    commit = object_read(repo, sha)
    assert commit.fmt == b"commit"

    if not b"parent" in commit.kvlm.keys():
        # Base case: the initial commit.
        return

    parents = commit.kvlm[b"parent"]

    if type(parents) != list:
        parents = [parents]

    for p in parents:
        p = p.decode("ascii")
        print("c_{0} -> c_{1};".format(sha, p))
        log_graphviz(repo, p, seen)


class GitTreeLeaf(object):
    def __init__(self, mode, path, sha):
        self.mode = mode
        self.path = path
        self.sha = sha


def tree_parse_one(raw, start=0):
    # A parser to extract a single record,
    # which returns parsed data
    # and the position it reached in input data

    # Find the space terminator of the mode
    x = raw.find(b" ", start)
    assert x - start == 5 or x - start == 6

    # Read the mode
    mode = raw[start:x]

    # Find the Null terminator of the path
    y = raw.find(b"\x00", x)
    # and read the path
    path = raw[x + 1 : y]

    # Read the SHA and convert to an hex string
    sha = hex(
        int.from_bytes(
            # from_bytes return integer from bytes.
            # hex() adds 0x in front and we don't want that
            raw[y + 1 : y + 21],
            "big",
        )
    )[2:]

    return y + 21, GitTreeLeaf(mode, path, sha)


def tree_parse(raw):
    # tree_parse calls tree_parse_one until input data is exhausted
    pos = 0
    max = len(raw)
    ret = list()
    while pos < max:
        pos, data = tree_parse(raw, pos)
        ret.append(data)
    return ret


def tree_serialize(obj):
    # tree_serializer serialise tree object to bytes
    # 100644 894a44cc066a027465cd26d634948d56d13af9af .gitignore
    ret = b""
    for i in obj.items:
        ret += i.mode
        ret += b" "
        ret += i.path
        ret += b"\x00"
        sha = int(i.sha, 16)

        ret += sha.to_bytes(20, byteorder="big")
    return ret


class GitTree(GitObject):
    fmt = b"tree"

    def deserialize(self, data):
        self.items = tree_parse(data)

    def serialize(self):
        return tree_serialize(self)


# ls-tree command
argsp = argsubparsers.add_parser("ls-tree", help="Pretty-print a tree object.")
argsp.add_argument("object", help="The object to show.")


def cmd_ls_tree(args):
    repo = repo_find()
    obj = object_read(repo, object_find(repo, args.object, fmt=b"tree"))

    for item in obj.items:
        print(
            "{0} {1} {2}\t{3}".format(
                "0" * (6 - len(item.mode)) + item.mode.decode("ascii"),
                # Git's ls-tree displays the type
                # of the object pointed to.  We can do that too :)
                object_read(repo, item.sha).fmt.decode("ascii"),
                item.sha,
                item.path.decode("ascii"),
            )
        )


argsp = argsubparsers.add_parser(
    "checkout", help="Checkout a commit inside of a directory."
)

argsp.add_argument("commit", help="The commit or treee to checkout.")
argsp.add_argument("path", help="The EMPTY directory to checkout on.")


def cmd_checkout(args):
    # A wrapper class for instantiating a tree directory of a specific commit in the specified directory
    repo = repo_find()

    obj = object_read(repo, object_find(repo, args.commit))

    # If the object is a commit, we grab its tree
    if obj.fmt == b"commit":
        obj = object_read(repo, obj.kvlm[b"tree"].decode("ascii"))

    # Verify that path is an empty directory and exist. Else we create the directory
    if os.path.exists(args.path):
        if not os.path.isdir(args.path):
            raise Exception("Not a directory: {0}".format(args.path))
        if os.listdir(args.path):
            raise Exception("Not empty {0}".format(args.path))
    else:
        os.makedirs(args.path)

    tree_checkout(repo, obj, os.path.realpath(args.path).encode())


def tree_checkout(repo, tree, path):
    for item in tree.items:
        obj = object_read(repo, item.sha)
        dest = os.path.join(path, item.path)

        if obj.fmt == b"tree":
            os.mkdir(dest)
            tree_checkout(repo, obj, dest)
        elif obj.fmt == b"blob":
            with open(dest, "wb") as f:
                f.write(obj.blobdata)


def ref_resolve(repo, ref):
    # A recursive solver that takes a ref name,
    # then follow eventual recurisve reference (refs whose content begin with "ref:")
    # and return a SHA-1
    # A ref: refs/remotes/origin/master
    with open(repo_file(repo, ref), "r") as fp:
        data = fp.read()[:-1]  # drop the final \n
    if data.startwith("ref: "):
        return ref_resolve(repo, data[5:])
    else:
        return data


def ref_list(repo, path=None):
    # A recursive function to collect refs and return them as a dict
    if not path:
        path = repo_dir(repo, "ref")
    ret = collections.OrderedDict()
    # Git shows refs sorted.
    # To do the same, we use an OrderedDict and sort the output of listdir
    for f in sorted(os.listdir(path)):
        can = os.path.join(path, f)  # path to dir
        if os.path.isdir(can):  # if dir, recursive call
            ret[f] = ref_list(repo, can)
        else:
            ret[f] = ref_resolve(repo, can)

    return ret


argsp = argsubparsers.add_parser("show-ref", help="List referneces.")


def cmd_show_ref(args):
    # this function is called when user uses git show-ref. 
    # Show-ref shows the reference of branch to the git object from a .git/refs file
    repo = repo_find()
    refs = ref_list(repo)
    show_ref(repo, refs, prefix="ref")


def show_ref(repo, refs, with_hash=True, prefix=""):
    for k, v in refs.items():
        if type(v) == str:
            print(
                "{0}{1}{2}".format(
                    v + " " if with_hash else "", prefix + "/" if prefix else "", k
                )
            )
        else:
            show_ref(
                repo,
                v,
                with_hash,
                prefix="{0}{1}{2}".format(prefix, "/" if prefix else "", k),
            )
