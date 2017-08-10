#!/usr/bin/env python
import logging
import os
import sys

TEST_MODE = (sys.argv[0].split('/')[-1] == 'py.test')
try:
    import collectd
except ImportError:
    if not TEST_MODE:
        raise

from cephmetrics_collectors import (Ceph, common, iscsi, mon, osd, rgw)

__author__ = 'Paul Cuzner'

PLUGIN_NAME = 'cephmetrics'


def write_stats(role_metrics, stats):

    flat_stats = common.flatten_dict(stats, '.')
    for key_name in flat_stats:
        attr_name = key_name.split('.')[-1]

        # TODO: this needs some more think time, since the key from the name
        # is not the key of the all_metrics dict
        if attr_name in role_metrics:
            attr_type = role_metrics[attr_name][1]     # gauge / derive etc
        else:
            # assign a default
            attr_type = 'gauge'

        attr_value = flat_stats[key_name]

        val = collectd.Values(plugin=PLUGIN_NAME, type=attr_type)
        instance_name = "{}.{}".format(CEPH.cluster_name,
                                       key_name)
        val.type_instance = instance_name
        val.values = [attr_value]
        val.dispatch()


def configure_callback(conf):

    valid_log_levels = ['debug', 'info']

    global CEPH
    module_parms = {node.key: node.values[0] for node in conf.children}

    log_level = module_parms.get('LogLevel', 'debug')
    if log_level not in valid_log_levels:
        collectd.error("LogLevel specified is invalid - must"
                       " be :{}".format(' or '.join(valid_log_levels)))

    if 'ClusterName' in module_parms:
        cluster_name = module_parms['ClusterName']
        # cluster name is all we need to get started
        if not os.path.exists('/etc/ceph/{}.conf'.format(cluster_name)):
            collectd.error("Clustername given ('{}') not found in "
                           "/etc/ceph".format(module_parms['ClusterName']))

        # let's assume the conf file is OK to use
        CEPH.cluster_name = cluster_name

        setup_module_logging(log_level)

        CEPH.probe()
        collectd.info(
            "{}: Roles detected - mon:{} osd:{} rgw:{} iscsi:{}".format(
                __name__,
                isinstance(CEPH.mon, mon.Mon),
                isinstance(CEPH.osd, osd.OSDs),
                isinstance(CEPH.rgw, rgw.RGW),
                isinstance(CEPH.iscsi, iscsi.ISCSIGateway),
            ))

    else:
        collectd.error("ClusterName is required")


def setup_module_logging(log_level, path='/var/log/collectd-cephmetrics.log'):

    level = {"debug": logging.DEBUG,
             "info": logging.INFO}

    logging.getLogger('cephmetrics')
    log_conf = dict(
        format='%(asctime)s - %(levelname)-7s - '
               '[%(filename)s:%(lineno)s:%(funcName)s() - '
               '%(message)s',
        level=level.get(log_level)
    )
    if path:
        log_conf['filename'] = path
    logging.basicConfig(**log_conf)


def read_callback():

    if CEPH.mon:
        mon_stats = CEPH.mon.get_stats()
        write_stats(mon.Mon.all_metrics, mon_stats)

    if CEPH.rgw:
        rgw_stats = CEPH.rgw.get_stats()
        write_stats(rgw.RGW.all_metrics, rgw_stats)

    if CEPH.osd:
        osd_node_stats = CEPH.osd.get_stats()
        write_stats(osd.OSDs.all_metrics, osd_node_stats)

    if CEPH.iscsi:
        iscsi_stats = CEPH.iscsi.get_stats()
        write_stats(iscsi.ISCSIGateway.metrics, iscsi_stats)


if TEST_MODE:
    pass
else:
    CEPH = Ceph()
    collectd.register_config(configure_callback)
    collectd.register_read(read_callback)