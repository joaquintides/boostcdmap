# boostcccdep: Boost conditional dependency calculator based
# on a compiler driver
#
# Copyright 2020 Joaquin M Lopez Munoz.
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)
#
# See https://github.com/joaquintides/boostcdmap/ for project home page.

import argparse
import os
import re
import sys

parser=argparse.ArgumentParser(description="Boost conditional dependency calculator")
parser.add_argument(
  "-b","--boost-root",metavar="<path-to-boost>",
  dest="path_to_boost",default=os.environ.get("BOOST_ROOT"),
  help="path to Boost (default uses BOOST_ROOT environment variable)")
parser.add_argument(
  "-std",metavar="<std>",
  dest="std",required=True,
  help="C++ standard version used")
parser.add_argument(
  "-D",metavar="<pp-symbol>",
  dest="symbols",action="append",
  help="predefined preprocessor symbol (can be used multiple times)")
parser.add_argument(
  "-v","--verbose",action="store_true",help="verbose mode")
parser.add_argument(
  "compiler",metavar="<compiler>",help="compiler command name (vg. compiler++)")
parser.add_argument(
  "module",metavar="<module>",help="Boost module name")
args=parser.parse_args()

boost_root=args.path_to_boost
if not boost_root:
  sys.stderr.write("Path to Boost not available\n")
  exit(1)
if not os.path.exists(boost_root):
  sys.stderr.write("Can't find "+boost_root+"\n")
  exit(1)
boost_root=os.path.abspath(boost_root)
boost_root_libs=os.path.join(boost_root,"libs")
modules=filter(
  lambda x: os.path.isdir(os.path.join(boost_root_libs,x)),
  os.listdir(boost_root_libs))
modules.remove("headers") # fake module
include_path={module:os.path.join(boost_root_libs,module,"include")
              for module in modules}
src_path={module:os.path.join(boost_root_libs,module,"src")
              for module in modules}

std_option="-std="+args.std
compiler=args.compiler

if os.system(" ".join((compiler,"-v",">nul","2>nul")))!=0:
  sys.stderr.write("Can't execute {}\n".format(compiler))
  exit(1)

compiler_cfg_filename="compiler_cfg.txt"
compiler_out_filename="compiler_out.txt"

with open(compiler_cfg_filename,"w") as wave_cfg:
  wave_cfg.write("-E\n")
  wave_cfg.write("--trace-includes\n")
  wave_cfg.write(std_option+"\n")
  if args.symbols:
    for symbol in args.symbols: wave_cfg.write("-D"+symbol+"\n")
  for module in modules:
    wave_cfg.write("-I"+include_path[module]+"\n")
            
verbose_mode=args.verbose
dependencies=set()

def add_dependencies_file(filename):
  os.system(" ".join((
    compiler,"@"+compiler_cfg_filename,filename,">nul","2>"+compiler_out_filename)))
  with open(compiler_out_filename,"r") as compiler_out:
    pattern="^\.+ (.+)$"
    for line in compiler_out.readlines():
      match=re.match(pattern,line)
      if match:
        path=match.group(1)
        for module in modules:
          if os.path.commonprefix([include_path[module],path])==include_path[module]:
            dependencies.add(module)
            break

def add_dependencies_dir(path):
  admitted_extensions={".h",".c",".hpp",".cpp",".hh",".cc",".h+",".c+",".h++",".c++"}
  excluded_subdirs={"detail","impl"}
  for dirpath, dirnames, filenames in os.walk(path):
    dirnames[:]=[d for d in dirnames if d not in excluded_subdirs]
    for filename in filenames:
      if not os.path.splitext(filename)[1].lower() in admitted_extensions: continue
      if verbose_mode:
        sys.stdout.write(
          os.path.relpath(os.path.join(dirpath,filename),boost_root_libs)+"\n")
      add_dependencies_file(os.path.join(dirpath,filename))

target_module=args.module
if not target_module in modules:
  sys.stderr.write("Can't find module "+target_module+"\n")
  exit(1)  

if verbose_mode: sys.stdout.write("Scanning dependencies...\n")
add_dependencies_dir(os.path.join(include_path[target_module]))
add_dependencies_dir(os.path.join(src_path[target_module]))
dependencies.discard(target_module)
if verbose_mode: sys.stdout.write("Dependencies for module "+target_module+":\n")
for module in sorted(dependencies): sys.stdout.write(module+"\n")
if os.path.exists(compiler_out_filename): os.remove(compiler_out_filename)
if os.path.exists(compiler_cfg_filename): os.remove(compiler_cfg_filename)

