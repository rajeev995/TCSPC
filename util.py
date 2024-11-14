import re
import os
import sys
import functools
import itertools
import collections
import statistics
import math
import matplotlib as mpl
import matplotlib.colors
import matplotlib.cm as cm
import numpy
import sys
sys.path.append(r"c:\Users\Rajeev\OneDrive\Desktop\photon_correlation-master\python")
import photon_correlation as pc
filename_parser = re.compile(r"(?P<dot_number>[a-zA-Z0-9]+)")
dot_number_parser = re.compile(r"(?P<index>\d+)(?P<modifier>[a-zA-Z]*)")
si_prefixes = {-9: r"\nano",
               -6: r"\micro",
               -3: r"\milli",
               0: "",
               3: r"\kilo",
               6: r"\mega",
               9: r"\giga",
               "n": r"\nano",
               "u": r"\micro"}
si_magnitude = {"n": 1e-9,
                "u": 1e-6}

CMRmap = matplotlib.colors.ListedColormap(
    list(reversed(
        [(0, 0, 0), (0.15, 0.15, 0.5), (0.3, 0.15, 0.75),
         (0.6, 0.2, 0.50), (0.1, 0.25, 0.15), (0.9, 0.5, 0),
         (0.9, 0.75, 0.1), (0.9, 0.9, 0.5), (1, 1, 1)])))

def repetition_rate_pformat(repetition_rate):
    """
    For the input count rate, produce the LaTeX version (for siunitx) of the
    rounded value.
    """
    magnitude = math.floor(math.log(repetition_rate)/math.log(10)/3)*3
    value = repetition_rate/10**magnitude
    if value < 100:
        value = "{0:.1f}".format(value)
    else:
        value = round(value)

    prefix = si_prefixes[magnitude]
    suffix = r"\hertz"
    return(r"\SI" + r"{{{}}}".format(value) +
           r"{{{0}{1}}}".format(prefix, suffix))

def power_pformat(power):
    """
    For the reported power, produce the LaTeX version (for siunitx).
    """
    parsed = re.search(r"(?P<value>[\.0-9]+)(?P<prefix>[A-Za-z])W", power)

    value = round(float(parsed.group("value")))
    prefix = si_prefixes[parsed.group("prefix")]
    suffix = r"\watt"
    return(r"\SI" + r"{{{}}}".format(value) +
           r"{{{0}{1}}}".format(prefix, suffix))

def power_float(power):
    parsed = re.search(r"(?P<value>[\\.0-9]+)(?P<prefix>[A-Za-z])W", power)
    value = float(parsed.group("value"))
    magnitude = si_magnitude[parsed.group("prefix")]

    return(value*magnitude)

def factorial(n):
    return(functools.reduce(lambda x, y: x*y, range(1, n+1), 1.0))

def get_colors(n, lower=None, upper=None, colormap=cm.rainbow):
    if lower is None:
        lower = 0
        
    if upper is None:
        upper = 1
        
    return(colormap(numpy.linspace(lower, upper, n)))

def dot_number(filename):
    raw = filename_parser.search(filename).group("dot_number")
    parsed = dot_number_parser.search(raw)

    return(int(parsed.group("index")), parsed.group("modifier"))

def normalize(L, key=max):
    my_key = key(L)

    if my_key == 0:
        my_key = 1

    return(list(map(lambda x: x/float(my_key), L)))

def first_index(L, value):
    """
    Find the first occurrence of value in L.
    """
    val = next(iter(filter(lambda x: x[1] == value, enumerate(L))))

    if val:
        return(val[0])
    else:
        raise(ValueError("{} is not in the list.".format(value)))

def last_index(L, value):
    """
    Find the final occurrence of value in L.
    """
    val = next(iter(
        filter(lambda x: x[1] == value, reversed(list(enumerate(L))))))

    if val:
        return(val[0])
    else:
        raise(ValueError("{} is not in the list.".format(value)))

def is_cross_correlation(correlation):
    return(len(set(correlation)) == len(correlation))

def common_name(filename):
    my_filename = filename
    root = filename
    found_data = False
    while not found_data:
        if not root:
            raise(ValueError("Filename does not appear to "
                             "correspond to a dot: {}".format(filename)))
        
        root, my_filename = os.path.split(my_filename)
        
        if filename_parser.search(my_filename):
            found_data = True
        else:
            my_filename = root
             
    root, date = os.path.split(root)

    return("{}_{}".format(date, re.sub(r"\.ht[23]*", "", my_filename)))

def rebin(L, n=2):
    """
    Group every n elements, and add them together. Division by n creates
    the boxcar average.
    """
    result = list()
    
    for i in range(len(L)//n):
        result.append(sum(L[(i*n):((i+1)*n)]))

    return(result)

def smooth(L, n=2):
    """
    Perform a boxcar average with width n. Return the result as a new
    lifetime object.
    """
    return(list(map(lambda x: float(x)/n, rebin(list(L), n=n))))

def final_nonzero(L):
    """
    Return the index of the last non-zero value in the list.
    """
    for index, val in reversed(list(enumerate(L))):
        if val:
            return(index)

    return(0)

def transpose(L):
    length = len(L[0])

    for i in range(length):
        yield(list(map(lambda x: x[i], L)))

def ps_to_ns(L):
    return(list(map(lambda x: x*1e-3, L)))

def make_gn_stream(bins, counts):
    """
    Given the bins (header) and counts (row) of a single line of a gn.td run,
    rotate the result to produce the stream appropriate for the gn file format.
    """
    for my_bin, my_counts in zip(numpy.transpose(bins),
                                 numpy.transpose(counts)):
        yield(list(my_bin) + [my_counts])

def neighbor_normalize(times, counts):
    """
    Use the distance between nearest neighbors to add a correction to the
    normalization of the counts.
    """
    new_times = list()
    new_counts = list()

    # Start away from the ends to make sure that we do not try to look outside
    # the list
    for index, vals in enumerate(zip(times, counts[1:-2])):
        t, c = vals
        
        if c != 0:
            left = None
            right = None

            for left_index in reversed(range(index)):
                if counts[left_index] != 0:
                    left = left_index
                    break

            for right_index in range(index+1, len(counts)):
                if counts[right_index] != 0:
                    right = right_index
                    break
  
            if left is not None and right is not None:
                dt = statistics.mean(times[right]) - \
                     statistics.mean(times[left])
                new_left = statistics.mean([statistics.mean(times[left]),
                                            statistics.mean(t)])
                new_right = statistics.mean([statistics.mean(t),
                                             statistics.mean(times[right])])
                new_times.append((new_left, new_right))
                new_counts.append(c/(dt*2.0))

    return(new_times, new_counts)

def unique_dots(dots):
    """
    Group distinct runs for single dots to enable averaging over all data.
    """
    keys = set(map(lambda x: x.dot_key(), dots))

    for key in sorted(keys):
        yield(list(filter(lambda x: x.dot_key() == key, dots)))

def unique_dot_keys(experiment_keys):
    """
    Return the first run of each dot, given all experiments.
    """
    result = list()
        
    for key in sorted(experiment_keys):
        if key[:2] not in map(lambda x: x[:2], result):
            result.append(key)

    return(result)

def dot_index(dot, dots_dict):
    """
    Determine the absolute index of the dot, given the dict of dots. Index
    starts at 1.
    """
    keys = list(sorted(set(map(lambda x: x[:2], dots_dict.keys()))))
    return(keys.index(dot.dot_key())+1)

def flatten(LoL):
    return(list(itertools.chain.from_iterable(LoL)))

def pnrl_2_from_signals(*signals, times=None, correlate=False):
    """
    Determine the form of the PNRL(2) signal which results from the combination
    of independent signals. This includes all time orderings.

    If times are specified, the output signals for the first and second
    photons are given as lifetime objects.

    If correlate is specified, then the signals are correlated as possible:
    first is still absolute time, and the second photon is the time relative
    to the first (convolution)
    """
    signals = list(map(numpy.array, signals))
    first = numpy.zeros(len(signals[0]))
    second = numpy.zeros(len(signals[0]))

    for src, dst in itertools.permutations(signals, r=2):
        before = 0
        after = sum(dst)

        for index, (left, right) in enumerate(zip(src, dst)):
            first[index] += left*after

            if not correlate:
                second[index] += before*right

            before += left
            after -= right

        if correlate:
            second += numpy.convolve(src, dst[::-1])[(len(src)-1):]

    if times is None:
        return(first, second)
    else:
        return(pc.Lifetime(first, times=times),
               pc.Lifetime(second, times=times))

def pnrl_3_from_signals(*signals, times=None):
    """
    Determine the form of the PNRL(3) signal which results from the combination
    of independent signals. This includes all time orderings.

    If times are specified, the output signals for the first and second
    photons are given as lifetime objects.
    """
    first = numpy.zeros(len(signals[0]))
    second = numpy.zeros(len(signals[0]))
    third = numpy.zeros(len(signals[0]))
    
    for s0, s1, s2 in itertools.permutations(signals, r=3):
        before = 0
        after = [sum(s1), sum(s2)]

        for index, (left, middle, right) in enumerate(zip(s0, s1, s2)):
            first[index] += left * after[0] * after[1] 
            second[index] += before * middle * after[1] *2
            third[index] += before * before * right 

            before += left
            after[0] -= middle
            after[1] -= right

    if times is None:
        return(first, second, third)
    else:
        return(pc.Lifetime(first, times=times),
               pc.Lifetime(second, times=times),
               pc.Lifetime(third, times=times))
##
##def pnrl_4_from_signals(*signals, times=None):
##    """
##    Determine the form of the PNRL(3) signal which results from the combination
##    of independent signals. This includes all time orderings.
##
##    If times are specified, the output signals for the first and second
##    photons are given as lifetime objects.
##    """
##    first = numpy.zeros(len(signals[0]))
##    second = numpy.zeros(len(signals[0]))
##    third = numpy.zeros(len(signals[0]))
##    fourth = numpy.zeros(len(signals[0]))
##    
##    for s0, s1, s2, s3 in itertools.permutations(signals, r=4):
##        before = 0
##        after = [sum(s1), sum(s2), sum(s3)]
##
##        for index, (one, two, three, four) in enumerate(zip(s0, s1, s2, s3)):
##            first[index] += one * after[0] * after[1] * after[2] 
##            second[index] += before * two * after[1] * after[2] * 3
##            third[index] += before * before * three * after[2] * 3
##            fourth[index] += before * before * before * four
##
##            before += one
##            after[0] -= two
##            after[1] -= three
##            after[2] -= four
##            
##
##    if times is None:
##        return(first, second, third, fourth)
##    else:
##        return(pc.Lifetime(first, times=times),
##               pc.Lifetime(second, times=times),
##               pc.Lifetime(third, times=times),
##               pc.Lifetime(fourth, times=times))
