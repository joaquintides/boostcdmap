# boostcdmap: Boost conditional dependency map generator
#
# Copyright 2020 Joaquin M Lopez Munoz.
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)
#
# See https://github.com/joaquintides/boostcdmap/ for project home page.

import argparse
import copy
import json
import multiprocessing
import os
import re
import sys

parser=argparse.ArgumentParser(
  description="Boost conditional dependency map generator")
parser.add_argument(
  "-b","--boost-root",metavar="<path-to-boost>",
  dest="path_to_boost",default=os.environ.get("BOOST_ROOT"),
  help="path to Boost (default uses BOOST_ROOT environment variable)")
parser.add_argument(
  "mincxx_info",metavar="<mincxx-info-file>",
  help="path to JSON file with info on min C++ requirements for Boost libs")
args=parser.parse_args()

boost_root=args.path_to_boost
if not boost_root:
  sys.stderr.write("Path to Boost not available\n")
  exit(1)
if not os.path.exists(boost_root):
  sys.stderr.write("Can't find "+boost_root+"\n")
  exit(1)
boost_root_libs=os.path.join(boost_root,"libs")
libs_path=re.compile(r"^\s*path\s*=*\slibs/(\S*)\s*$")
with open(os.path.join(boost_root,".gitmodules"),"r") as gitmodules:
  modules=sorted({
    m.group(1) for m in map(libs_path.match,gitmodules.readlines()) if m})

mincxx_info=args.mincxx_info
if not os.path.exists(mincxx_info):
  sys.stderr.write("Can't find "+mincxx_info+"\n")
  exit(1)
with open(mincxx_info,"r") as file:
  mincxx=json.load(file)

compiler="clang++-10"
configs=[("03","-std=c++98"),("11","-std=c++11"),("14","-std=c++14"),
         ("17","-std=c++17"),("20","-std=c++2a")]
header_dependencies={module:dict() for module in modules}
source_dependencies={module:dict() for module in modules}
dependencies_to_expand={module:dict() for module in modules}

#if os.system("python boostccdep.py -h >nul")!=0:
#  sys.stderr.write("Can't execute boostccdep.py\n")
#  exit(1)

def scan_dependencies(module,cxx_no,std_option):
  header_section=re.compile(r"^\s*From headers:\s*$")
  source_section=re.compile(r"^\s*From sources:\s*$")
  report_filename="boostccdep_out_{}.txt".format(os.getpid())
  header_deps=[]
  source_deps=[]
  deps=None
  if os.system(" ".join((
    "python boostccdep.py","--boost-root","\""+boost_root+"\"",
    "-DBOOST_ASSUME_CXX="+cxx_no,std_option,compiler,module,
    ">"+report_filename)))==0:
    with open(report_filename,"r") as file:
      for line in file.readlines():
        if header_section.match(line): deps=header_deps
        elif source_section.match(line): deps=source_deps
        elif deps!=None: deps.append(line.strip())
  os.remove(report_filename)
  return header_deps,source_deps,copy.deepcopy(source_deps)

def total_dependencies(module,cxx_no):
  # need to expand
  return sorted(set(
    header_dependencies[module][cxx_no]+source_dependencies[module][cxx_no]))

if __name__=="__main__":
  p=multiprocessing.Pool(3*multiprocessing.cpu_count())
  tasks=dict()
  for module in modules:
    for cxx_no,std_option in configs:
      if module in mincxx and int(cxx_no)<int(mincxx[module]): continue
      tasks.setdefault(module,[]).append(
        (cxx_no,p.apply_async(scan_dependencies,(module,cxx_no,std_option))))

  sys.stderr.write("Scanning dependencies...\n")
  for module in modules:
    next_cxx_sep=""
    sys.stderr.write("{}: ".format(module))
    for cxx_no,async_result in tasks[module]:
      sys.stderr.write("{}{}".format(next_cxx_sep,cxx_no))
      next_cxx_sep=", "
      ( header_dependencies[module][cxx_no],
        source_dependencies[module][cxx_no],
        dependencies_to_expand[module][cxx_no] )=async_result.get()
    sys.stderr.write("\n")

  next_module_sep=""
  for module in modules:
    sys.stdout.write("{}  \"{}\": {{\n".format(next_module_sep,module))
    next_module_sep=",\n"
    next_cxx_sep=""
    for cxx_no,_ in tasks[module]:
      sys.stdout.write("{}    \"{}\": [".format(next_cxx_sep,cxx_no))
      next_cxx_sep=",\n"
      sys.stdout.write(", ".join("\"{}\"".format(dep)
                                 for dep in total_dependencies(module,cxx_no)))
      sys.stdout.write("]")
    sys.stdout.write("\n  }")
  sys.stdout.write("\n}\n")
