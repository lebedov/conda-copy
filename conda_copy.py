#!/usr/bin/env python

"""
Copy conda environments.
"""

import argparse
import json
import os
import re
import shutil
from subprocess import Popen, PIPE
import sys

from binaryornot.check import is_binary
import glob2

parser = argparse.ArgumentParser()
parser.add_argument('old', help='Original environment to copy')
parser.add_argument('new', help='Name to assign new environment')
args = parser.parse_args()

# From commented-out code in conda-api:
def get_conda_path():
    plat = 'posix'
    if sys.platform.lower().startswith('win'):
        listsep = ';'
        plat = 'win'
    else:
        listsep = ':'    
    for d in os.environ['PATH'].split(listsep):
        if os.path.exists(os.path.join(d, 'conda')):
            return os.path.join(d, 'conda')
        elif os.path.exists(os.path.join(d, 'conda.exe')): 
            return os.path.join(d, 'conda.exe')
        elif os.path.exists(os.path.join(d, 'conda.bat')):
            return os.path.join(d, 'conda.bat')
    return ''

def _call_conda(conda_path, extra_args, abspath=True):

    # Get directory containing python and conda script:
    if not conda_path:
        raise ValueError('cannot find conda')
    bin_dir = os.path.dirname(conda_path)

    # Call conda with the list of extra arguments, and return the tuple
    # stdout, stderr
    if abspath:
        # XXX The paths for Windows might not be correct:
        if sys.platform == 'win32':
            python = os.path.join(bin_dir, 'python.exe')
            conda  = os.path.join(bin_dir, 'Scripts', 'conda-script.py')
        else:
            python = os.path.join(bin_dir, 'python')
            conda  = os.path.join(bin_dir, 'conda')

        # If the conda path is a symlink, we have to find the actual path of the
        # original conda script and the python executable:
        if os.path.islink(conda):
            conda = os.path.realpath(conda)
            python = os.path.join(os.path.dirname(conda),
                                  os.path.basename(python))

        cmd_list = [python, conda]
    else:
        # Execute the conda command on the path directly:
        cmd_list = ['conda']

    cmd_list.extend(extra_args)

    try:
        p = Popen(cmd_list, stdout=PIPE, stderr=PIPE)
    except OSError:
        raise Exception("could not invoke %r\n" % args)
    return p.communicate()

def replace_str(f, old_str, new_str):
    old_stats = os.stat(f)

    h = open(f, 'rb')
    old_data = h.read()
    h.close()

    new_data = re.sub(old_str, new_str, old_data)
    h = open(f, 'wb')
    h.write(new_data)

    h.close()

    os.chmod(f, old_stats.st_mode)
    os.chown(f, old_stats.st_uid, old_stats.st_gid)
    os.utime(f, (old_stats.st_atime, old_stats.st_mtime))

conda_path = get_conda_path()
info = json.loads(_call_conda(conda_path, ['info', '--json'])[0])

# Check that the old environment actually exists:
for d in info['envs_dirs']:
    if os.path.exists(os.path.join(d, args.old)):
        old_dir = os.path.join(d, args.old)
        break
else:
    print '%s does not exist' % args.old
    sys.exit(1)

# Check that the new environment does not yet exist:
for d in info['envs_dirs']:
    if os.path.exists(os.path.join(d, args.new)):
        print '%s already exists' % args.new
        sys.exit(1)
new_dir = os.path.join(info['envs_dirs'][0], args.new)

# Copy the old environment:
try:
    shutil.copytree(old_dir, new_dir, True)
except:
    print 'error copying original environment'
    try:
        shutil.rmtree(new_dir)
    except:
        pass
    sys.exit(1)

# Find all files in the new environment:
file_list = glob2.glob(os.path.join(new_dir, '**'))

# Don't attempt to modify files that are links:
for old_file in file_list:
    if not os.path.islink(old_file) and \
       not os.path.isdir(old_file) and \
       not is_binary(old_file):
        replace_str(old_file, old_dir, new_dir)
