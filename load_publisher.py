#!/usr/bin/env python
"""
The MIT License

Copyright (c) 2013 ReMake Electric ehf

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import argparse
import logging
import multiprocessing
import os
import beem.load

logging.basicConfig(level=logging.INFO)

def custom_make_topic(seq):
    """
    An example of a custom topic generator.

    Any string at all can be returned, the sequence number is the sequence
    within the process
    """
    return "karlosssssss_%d" % seq

def custom_make_payload(seq, size):
    return "Message %d was meant to be %d bytes long hehe" % (seq, size)

def worker(options):
    """
    Wrapper to run a test and push the results back onto a queue.
    You may want to modify this to provide custom message generation routines
    """
    # Get the pid of _this_ process.
    cid = "%s-%d" % (options.clientid, os.getpid())
    ts = beem.load.TrackingSender(options.host, options.port, cid)
    # Provide a custom topic generator
    #ts.make_topic = custom_make_topic
    # Or a custom payload generator
    #ts.make_payload = custom_make_payload
    ts.run(options.msg_count, options.msg_size, options.qos)
    return ts.stats()


def print_stats(stats):
    """
    pretty print a stats object
    """
    print("Clientid: %s" % stats["clientid"])
    print("Message succes rate: %.2f%% (%d/%d messages)"
        % (100 * stats["rate_ok"], stats["count_ok"], stats["count_total"]))
    print("Message timing mean   %.2f ms" % stats["time_mean"])
    print("Message timing stddev %.2f ms" % stats["time_stddev"])
    print("Message timing min    %.2f ms" % stats["time_min"])
    print("Message timing max    %.2f ms" % stats["time_max"])

def aggregate_stats(stats_set):
    """
    For a set of per process stats, make some basic aggregated stats
    timings are a simple mean of the input timings. ie the aggregate
    "minimum" is the average of the minimum of each process, not the
    absolute minimum of any process.
    Likewise, aggregate "stddev" is a simple mean of the stddev from each
    process, not an entire population stddev.
    """
    mins = [x["time_min"] for x in stats_set]
    maxes = [x["time_max"] for x in stats_set]
    means = [x["time_mean"] for x in stats_set]
    stddevs = [x["time_stddev"] for x in stats_set]
    count_ok = sum([x["count_ok"] for x in stats_set])
    count_total = sum([x["count_total"] for x in stats_set])
    cid = "Aggregate stats (simple avg) for %d processes" % len(stats_set)
    return {
        "clientid": cid,
        "count_ok": count_ok,
        "count_total": count_total,
        "rate_ok": count_ok / count_total,
        "time_min": sum(mins) / len(mins),
        "time_max": sum(maxes) / len(maxes),
        "time_mean": sum(means) / len(means),
        "time_stddev": sum(stddevs) / len(stddevs)
    }


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="""
        Publish a stream of messages and capture statistics on their timing
        """)

    parser.add_argument(
        "-c", "--clientid", default="beem.loadr-%d" % os.getpid(),
        help="""Set the client id of the publisher, can be useful for acls
        Default has pid information appended
        """)
    parser.add_argument(
        "-H", "--host", default="localhost",
        help="MQTT host to connect to")
    parser.add_argument(
        "-p", "--port", type=int, default=1883,
        help="Port for remote MQTT host")
    parser.add_argument(
        "-q", "--qos", type=int, choices=[0, 1, 2],
        help="set the mqtt qos for messages published", default=1)
    parser.add_argument(
        "-n", "--msg_count", type=int, default=10,
        help="How many messages to send")
    parser.add_argument(
        "-s", "--msg_size", type=int, default=100,
        help="""Size of messages to send. This will be gaussian at (x, x/20)
unless the make_payload method is overridden""")
    parser.add_argument(
        "-P", "--processes", type=int, default=1,
        help="How many separate processes to spin up (multiprocessing)")

    options = parser.parse_args()

    pool = multiprocessing.Pool(processes=options.processes)
    result_set = [pool.apply_async(worker, (options,)) for x in range(options.processes)]
    remaining = options.processes

    stats_set = []
    while remaining > 0:
        print("Still waiting for results from %d process(es)" % remaining)
        try:
            # This will print results in order started, not order completed :|
            for result in result_set:
                s = result.get(timeout=0.5)
                remaining -= 1
                print_stats(s)
                stats_set.append(s)
        except multiprocessing.TimeoutError:
            pass

    agg_stats = aggregate_stats(stats_set)
    print_stats(agg_stats)


if __name__ == "__main__":
    main()
