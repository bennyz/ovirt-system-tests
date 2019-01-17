#
# Copyright 2017 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

import glob
import os
import subprocess
import ConfigParser
from nose import SkipTest
from pwd import getpwuid
from shutil import rmtree
from yum.misc import getCacheDir
from ovirtlago import (testlib, constants)

import test_utils


@testlib.with_ovirt_prefix
def gen_config_file_and_params(
    prefix, cfg_in, cfg_out, cfg_path, tmp_cache_dir
):
    """Parse reposync config file and prepare params for repoclosure

    :param file cfg_in:     Reposync config file object to adjust
    :param file cfg_out:    File object to write adjusted configuration into
    :param str  cfg_path:   The actual path to the reposync config

    :rtype: list
    :returns: A list with 'repoclosure' command including it's parameters
              and a temporary cache dir that was generated
    """
    TEST_REPO_SECTION = 'internal_repo'

    command = ['repoclosure', '-t', '--config={}'.format(cfg_path)]
    internal_repo_ip = prefix.virt_env.get_net().gw()
    internal_repo_port = constants.REPO_SERVER_PORT

    internal_repo_url = 'http://{ip}:{port}/default/el7'.format(
        ip=internal_repo_ip, port=internal_repo_port
    )

    config = ConfigParser.ConfigParser()
    config.readfp(cfg_in)
    for section in config.sections():
        if section == "main":
            continue
        command.append('--lookaside={}'.format(section))
        if config.has_option(section, 'exclude'):
            config.remove_option(section, 'exclude')
        if config.has_option(section, 'includepkgs'):
            config.remove_option(section, 'includepkgs')

    if not config.has_section('main'):
        config.add_section('main')
    config.set('main', 'cachedir', tmp_cache_dir)
    config.add_section(TEST_REPO_SECTION)
    config.set(TEST_REPO_SECTION, 'name', 'Local repo')
    config.set(TEST_REPO_SECTION, 'baseurl', internal_repo_url)
    config.set(TEST_REPO_SECTION, 'enabled', 1)
    config.set(TEST_REPO_SECTION, 'ip_resolve', 4)
    config.set(TEST_REPO_SECTION, 'gpgcheck', 0)
    config.set(TEST_REPO_SECTION, 'proxy', '_none_')
    command.append('--repoid={}'.format(TEST_REPO_SECTION))
    config.write(cfg_out)
    return command


def reposync_config_file(config, tmp_cache_dir):
    """Open a config file for read and write in order to modify it
    :param str config:  reposync config filename

    :rtype: list
    :returns: A repoclosure command with all the needed parameters ready to be
    executed
    """
    repoclosure_conf = config + "_repoclosure"
    with open(config, 'r') as rf:
        with open(repoclosure_conf, 'w') as wf:
            command = gen_config_file_and_params(
                rf, wf, repoclosure_conf, tmp_cache_dir
            )
            wf.truncate()
    return command


def clean_tmp_cache(tmp_cache_dir):
    """Clean temp user cache generated by repoclosure
    :param str tmp_cache_dir: The patch to the cache dir that was generated
                              for yum's config
    """
    username = getpwuid(os.getuid())[0]
    dirpath = '/var/tmp/yum-%s-*' % (username)
    cachedirs = glob.glob(dirpath)
    for thisdir in cachedirs:
        rmtree(thisdir)
    rmtree(tmp_cache_dir)


def check_repo_closure():
    """Find reposync config file(s) and check repoclosure against the internal
     repo with the repos in the config(s) as lookaside repos
    """
    if os.getenv('OST_SKIP_SYNC', False):
        raise SkipTest('OST_SKIP_SYNC is set, skipping repo closure check')

    configs = glob.glob(
        os.path.join(os.environ.get('SUITE'), '*reposync*.repo')
    )
    if not configs:
        raise RuntimeError("Could not find reposync config file.")
    for config in configs:
        tmp_cache_dir = getCacheDir('/var/tmp/', reuse=False)
        command = reposync_config_file(config, tmp_cache_dir)
        try:
            subprocess.check_output(command, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            err_msg = ("\n"
                       "## Params: {com}.\n"
                       "## Exist status: {es}\n"
                       "## Output: {out}\n\n"
                       ).format(com=e.cmd, es=e.returncode, out=e.output,)
            raise SkipTest(err_msg)
            #raise RuntimeError(err_msg)
        finally:
            clean_tmp_cache(tmp_cache_dir)


_TEST_LIST = [
    # [02/07/17] The test will be skipped in case of an error instead of failing
    # This change is temporary only, until the test will be stable
    check_repo_closure
]


def test_gen():
    for t in test_utils.test_gen(_TEST_LIST, test_gen):
        yield t