# boostccdep: Boost conditional dependency calculator based
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
libs_path=re.compile(r"^\s*path\s*=*\slibs/(\S*)\s*$")
with open(os.path.join(boost_root,".gitmodules"),"r") as gitmodules:
  modules=sorted({
    m.group(1) for m in map(libs_path.match,gitmodules.readlines()) if m})
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

compiler_cfg_filename="compiler_cfg_{}.txt".format(os.getpid())
compiler_out_filename="compiler_out_{}.txt".format(os.getpid())

with open(compiler_cfg_filename,"w") as compiler_cfg:
  compiler_cfg.write("-M\n")
  compiler_cfg.write("-MG\n")
  compiler_cfg.write(std_option+"\n")
  if args.symbols:
    for symbol in args.symbols: compiler_cfg.write("-D"+symbol+"\n")
  for module in modules:
    compiler_cfg.write("-I"+include_path[module]+"\n")
            
verbose_mode=args.verbose
header_dependencies=set()
source_dependencies=set()
mk_dependency=re.compile(r"[^\\ :\n]+(?:\\.[^\\ :\n]*)*")

def add_dependencies(filename,deps):
  os.system(" ".join((
    compiler,"@"+compiler_cfg_filename,"\""+filename+"\"",
    ">"+compiler_out_filename,"2>nul")))
  with open(compiler_out_filename,"r") as compiler_out:
    for line in compiler_out.readlines():
      for path in mk_dependency.findall(line):
        path=path.replace("\\ "," ")
        for module in modules:
          if os.path.commonprefix([include_path[module],path])==include_path[module]:
            deps.add(module)
            break

def add_header_dependencies(filename):
  add_dependencies(filename,header_dependencies)

def add_source_dependencies(filename):
  add_dependencies(filename,source_dependencies)

admitted_header_extensions={".h",".hpp",".hh",".h+",".h++"}
admitted_source_extensions={".c",".cpp",".cc",".c+",".c++"}
admitted_extensions=admitted_header_extensions|admitted_source_extensions
excluded_subdirs={"aux_","detail","impl","preprocessed"}

def add_dependencies_dir(path):
  all_header_tu_filename="compiler_in_{}.cpp".format(os.getpid())
  header_count=0
  max_header_count=100
  with open(all_header_tu_filename,"w") as all_header_tu:
    for dirpath, dirnames, filenames in os.walk(path):
      dirnames[:]=[d for d in dirnames if d not in excluded_subdirs]
      for filename in filenames:
        extension=os.path.splitext(filename)[1].lower()
        if not extension in admitted_extensions: continue
        filename_path=os.path.join(dirpath,filename)
        if verbose_mode:
          sys.stdout.write(os.path.relpath(filename_path,boost_root_libs)+"\n")
        if extension in admitted_header_extensions:
          all_header_tu.write("#include \"{}\"\n".format(filename_path))
          header_count+=1
          if header_count>=max_header_count:
            all_header_tu.close()
            add_header_dependencies(all_header_tu_filename)
            all_header_tu=open(all_header_tu_filename,"w")
            header_count=0
        else:
          add_source_dependencies(filename_path)
  add_header_dependencies(all_header_tu_filename)
  os.remove(all_header_tu_filename)

target_module=args.module
if not target_module in modules:
  sys.stderr.write("Can't find module "+target_module+"\n")
  exit(1)  

if verbose_mode: sys.stdout.write("Scanning dependencies...\n")
add_dependencies_dir(os.path.join(include_path[target_module]))
add_dependencies_dir(os.path.join(src_path[target_module]))
header_dependencies.discard(target_module)
source_dependencies.discard(target_module)
if verbose_mode: sys.stdout.write("Dependencies for module {}:\n".format(target_module))
if header_dependencies:
  sys.stdout.write("From headers:\n")
  for module in sorted(header_dependencies): sys.stdout.write(module+"\n")
if source_dependencies:
  sys.stdout.write("From sources:\n")
  for module in sorted(source_dependencies): sys.stdout.write(module+"\n")
if os.path.exists(compiler_out_filename): os.remove(compiler_out_filename)
if os.path.exists(compiler_cfg_filename): os.remove(compiler_cfg_filename)
