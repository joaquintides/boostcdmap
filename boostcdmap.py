# boostcdmap: Boost conditional dependency map generator
#
# Copyright 2020 Joaquin M Lopez Munoz.
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)
#
# See https://github.com/joaquintides/boost_epoch/ for project home page.

import argparse
import json
import os
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
modules=filter(
  lambda x: os.path.isdir(os.path.join(boost_root_libs,x)),
  os.listdir(boost_root_libs))
modules.sort()
modules.remove("headers") # fake module

mincxx_info=args.mincxx_info
if not os.path.exists(mincxx_info):
  sys.stderr.write("Can't find "+mincxx_info+"\n")
  exit(1)
with open(mincxx_info,"r") as file:
  mincxx=json.load(file)

compiler="clang++-10"
configs=[("03","-std=c++98"),("11","-std=c++11"),("14","-std=c++14"),
         ("17","-std=c++17"),("20","-std=c++2a")]
report_filename="boostcccdep_out.txt"

if os.system("python boostcccdep.py -h >nul")!=0:
  sys.stderr.write("Can't execute boostcccdep.py\n")
  exit(1)

sys.stdout.write("{\n")
next_module_sep=""
for module in modules:
  sys.stdout.write("{}  \"{}\": {{\n".format(next_module_sep,module))
  next_module_sep=",\n"
  next_cxx_sep=""
  for cxx_no,std_option in configs:
    if module in mincxx and int(cxx_no)<int(mincxx[module]): continue
    sys.stdout.write("{}    \"{}\": [".format(next_cxx_sep,cxx_no))
    next_cxx_sep=",\n"
    if os.system(" ".join((
      "python boostcccdep.py","--boost-root","\""+boost_root+"\"",
      "-DBOOST_ASSUME_CXX="+cxx_no,std_option,compiler,module,
      ">"+report_filename)))!=0:
      exit(1)
    with open(report_filename,"r") as file:
      next_lib_sep=""
      for line in file.readlines():
        sys.stdout.write("{}\"{}\"".format(next_lib_sep,line.strip()))
        next_lib_sep=","
    sys.stdout.write("]")
  sys.stdout.write("\n  }")
sys.stdout.write("\n}\n")
