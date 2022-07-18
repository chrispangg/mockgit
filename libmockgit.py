import argparse, collections, configparser, hashlib, os, re, sys, zlib

# argparse - for parsing command-line arguments
# collections - for OrderedDict, which is not included in the base lib
# configparser - for reading and writing INI files
# hashlib - for SHA-1 which git uses heavily
# os - for accessing and manipulating the filesystem
# re - for regex
# sys - for accessing command line arg
# zlib - for compressing objects which git does as well

argparser = argparse.ArgumentParser(description="The stupid content tracker")
