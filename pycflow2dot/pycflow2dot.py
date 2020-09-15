# -*- coding: utf-8 -*-
"""Plot `cflow` output as graphs."""
# Copyright 2013-2020 Ioannis Filippidis
# Copyright 2010 unknown developer: https://code.google.com/p/cflow2dot/
# Copyright 2013 Dabaichi Valbendan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import argparse
import locale
import logging
import re
import subprocess
import sys

import networkx as nx
try:
    import pydot
except:
    pydot = None


_COLORS = ['#eecc80', '#ccee80', '#80ccee', '#eecc80', '#80eecc']
_DOT_RESERVED = {'graph', 'strict', 'digraph', 'subgraph', 'node', 'edge'}
logger = logging.getLogger(__name__)


def bytes2str(b):
    encoding = locale.getdefaultlocale()[1]
    return b.decode(encoding)


def get_max_space(lines):
    space = 0
    for i in range(0, len(lines)):
        if lines[i].startswith(space * 4 * ' '):
            i = 0
            space += 1
    return space


def get_name(line):
    name = ''
    for i in range(0, len(line)):
        if line[i] == ' ':
            pass
        elif line[i] == '(':
            break
        else:
            name += line[i]
    return name


def call_cflow(
        c_fname, cflow,
        numbered_nesting=True,
        preprocess=False,
        do_reverse=False):
    cflow_cmd = [cflow]
    if numbered_nesting:
        cflow_cmd.append('-l')
    # None when -p passed w/o value
    if preprocess is None:
        cflow_cmd.append('--cpp')
    elif preprocess:
        cflow_cmd.append('--cpp=' + preprocess)
    if do_reverse:
        cflow_cmd.append('--reverse')
    cflow_cmd.append(c_fname)
    logger.debug('cflow command:\n\t' + str(cflow_cmd))
    cflow_data = subprocess.check_output(cflow_cmd)
    cflow_data = bytes2str(cflow_data)
    logger.debug('cflow returned:\n\n' + cflow_data)
    return cflow_data


def cflow2dot_old(data, offset=False, filename=''):
    color = ['#eecc80', '#ccee80', '#80ccee', '#eecc80', '#80eecc']
    shape = ['box', 'ellipse', 'octagon', 'hexagon', 'diamond']
    dot = (
        'digraph G {{\n'
        'node [peripheries=2 style="filled,rounded" '
        'fontname="Vera Sans Mono" color="#eecc80"];\n'
        'rankdir=LR;\n'
        'label="{filename}"\n'
        'main [shape=box];\n').format(
            filename=filename)
    lines = data.replace('\r', '').split('\n')
    max_space = get_max_space(lines)
    nodes = set()
    edges = set()
    for i in range(0, max_space):
        for j in range(0, len(lines)):
            if lines[j].startswith((i + 1) * 4 * ' ') \
                    and not lines[j].startswith((i + 2) * 4 * ' '):
                cur_node = get_name(lines[j])
                # node already seen ?
                if cur_node not in nodes:
                    nodes.add(cur_node)
                    print('New Node: ' + cur_node)
                # predecessor \exists ?
                try:
                    pred_node
                except NameError:
                    raise Exception(
                        'No predecessor node defined yet! Buggy...')
                # edge already seen ?
                cur_edge = (pred_node, cur_node)
                if cur_edge not in edges:
                    edges.add(cur_edge)
                else:
                    continue
                dot += (('node [color="%s" shape=%s];edge [color="%s"];\n') % (
                        color[i % 5], shape[i % 5], color[i % 5]))
                dot += (pred_node + '->' + cur_node + '\n')
            elif lines[j].startswith(i * 4 * ' '):
                pred_node = get_name(lines[j])
            else:
                raise Exception('bug ?')
    dot += '}\n'
    logger.debug('dot dump str:\n\n' + dot)
    return dot


def cflow2nx(cflow_str, c_fname):
    lines = cflow_str.replace('\r', '').split('\n')
    g = nx.DiGraph()
    stack = dict()
    for line in lines:
        # logger.debug(line)
        # empty line ?
        if not line:
            continue
        # defined in this file ?
        # apparently, this check is not needed: check this better
        #
        # get source line #
        src_line_no = re.findall(':.*>', line)
        if src_line_no:
            src_line_no = int(src_line_no[0][1:-1])
        else:
            src_line_no = -1
        # trim
        s = re.sub(r'\(.*$', '', line)
        s = re.sub(r'^\{\s*', '', s)
        s = re.sub(r'\}\s*', r'\t', s)
        # where are we ?
        (nest_level, func_name) = re.split(r'\t', s)
        nest_level = int(nest_level)
        cur_node = rename_if_reserved_by_dot(func_name)
        logger.debug((
            'Found function:\n\t{func_name}'
            ',\n at depth:\n\t{nest_level}'
            ',\n at src line:\n\t{src_line_no}').format(
                func_name=func_name,
                nest_level=nest_level,
                src_line_no=src_line_no))
        stack[nest_level] = cur_node
        # not already seen ?
        if cur_node not in g:
            g.add_node(cur_node, nest_level=nest_level, src_line=src_line_no)
            logger.info('New Node: ' + cur_node)
        # not root node ?
        if nest_level != 0:
            # then has predecessor
            pred_node = stack[nest_level - 1]
            # new edge ?
            if g.has_edge(pred_node, cur_node):
                # avoid duplicate edges
                # note DiGraph is so def

                # buggy: coloring depends on first occurrence ! (subjective)
                continue
            # add new edge
            g.add_edge(pred_node, cur_node)
            logger.info(
                'Found edge:\n\t{pred_node}--->{cur_node}'.format(
                    pred_node=pred_node, cur_node=cur_node))
    return g


def rename_if_reserved_by_dot(word):
    # dot is case-insensitive, according to:
    #   http://www.graphviz.org/doc/info/lang.html
    if word.lower() in _DOT_RESERVED:
        word = word + '_'
    return word


def dot_preamble(c_fname, for_latex):
    c_fname = _graph_name_for_latex(c_fname, for_latex)
    d = _graph_node_defaults()
    node_defaults = ', '.join(
        '{k}={v}'.format(k=k, v=v) for k, v in d.items())
    dot_str = (
        'digraph G {{\n'
        'node [{node_defaults}];\n'
        'rankdir=LR;\n'
        'label="{c_fname}"\n'
        ).format(
            node_defaults=node_defaults,
            c_fname=c_fname)
    return dot_str


def _graph_name_for_latex(c_fname, for_latex):
    """Return graph name, with escaped underscores.

    Escape the underscores if `for_latex is True`.
    """
    if for_latex:
        c_fname = re.sub(r'_', r'\\\\_', c_fname)
    return c_fname


def _graph_node_defaults():
    """Return default properties of nodes."""
    return dict(
        peripheries="2", style='"filled,rounded"',
        fontname='"Vera Sans Mono"', color='"#eecc80"')


def choose_node_format(node, nest_level, src_line, defined_somewhere,
                       for_latex, multi_page):
    shapes = ['box', 'ellipse', 'octagon', 'hexagon', 'diamond']
    sl = '\\\\'  # after fprintf \\ and after dot \, a single slash !
    # color, shape ?
    if nest_level == 0:
        color = _COLORS[0]
        shape = 'box'
    else:
        color = _COLORS[(nest_level - 1) % 5]
        shape = shapes[nest_level % 5]
    # fix underscores ?
    label = _escape_underscores(node, for_latex)
    logger.debug('Label:\n\t: ' + label)
    # src line of def here ?
    if src_line != -1:
        if for_latex:
            label = '{label}\\n{src_line}'.format(
                label=label, src_line=src_line)
        else:
            label = '{label}\\n{src_line}'.format(
                label=label, src_line=src_line)
    # multi-page pdf ?
    if multi_page:
        if src_line != -1:
            # label
            label = sl + 'descitem{' + node + '}\\n' + label
        else:
            # link only if LaTeX label will appear somewhere
            if defined_somewhere:
                label = sl + 'descref[' + label + ']{' + node + '}'
    logger.debug('Node dot label:\n\t: ' + label)
    return (label, color, shape)


def _escape_underscores(s, for_latex):
    """If `for_latex`, then escape `_` in `s`."""
    if for_latex:
        s = re.sub(r'_', r'\\\\_', s)
    return s


def dot_format_node(node, nest_level, src_line, defined_somewhere,
                    for_latex, multi_page):
    label, color, shape = choose_node_format(
        node, nest_level, src_line,
        defined_somewhere,
        for_latex, multi_page)
    dot_str = (
        '{node}[label="{label}" '
        'color="{color}" shape={shape}];\n\n').format(
            node=node,
            label=label,
            color=color,
            shape=shape)
    return dot_str


def dot_format_edge(from_node, to_node, color):
    dot_str = (
        'edge [color="{color}"];\n\n'
        '{from_node}->{to_node}\n').format(
            color=color,
            from_node=from_node,
            to_node=to_node)
    return dot_str


def node_defined_in_other_src(node, other_graphs):
    defined_somewhere = False
    for graph in other_graphs:
        if node in graph:
            src_line = graph.nodes[node]['src_line']

            if src_line != -1:
                defined_somewhere = True
    return defined_somewhere


def dump_dot_wo_pydot(graph, other_graphs, c_fname, for_latex, multi_page):
    dot_str = dot_preamble(c_fname, for_latex)
    # format nodes
    for node in graph:
        node_dict = graph.nodes[node]
        defined_somewhere = node_defined_in_other_src(node, other_graphs)
        nest_level = node_dict['nest_level']
        src_line = node_dict['src_line']
        dot_str += dot_format_node(
            node, nest_level, src_line, defined_somewhere,
            for_latex, multi_page)
    # format edges
    for from_node, to_node in graph.edges():
        # call order affects edge color, so use only black
        color = '#000000'
        dot_str += dot_format_edge(from_node, to_node, color)
    dot_str += '}\n'
    logger.debug('dot dump str:\n\n' + dot_str)
    return dot_str


def write_dot_file(dot_str, dot_fname):
    try:
        dot_path = dot_fname + '.dot'
        with open(dot_path, 'w') as fp:
            fp.write(dot_str)
            logger.info('Dumped dot file.')
    except:
        raise Exception('Failed to save dot.')
    return dot_path


def _annotate_graph(
        graph, other_graphs, c_fname,
        for_latex, multi_page):
    """Return graph with labels, color, styles.

    @rtype: `networkx.DiGraph`
    """
    g = nx.DiGraph()
    graph_label = _graph_name_for_latex(c_fname, for_latex)
    g.graph['graph'] = dict(label=graph_label)
    g.graph['node'] = _graph_node_defaults()
    # annotate nodes
    for node in graph:
        defined_somewhere = node_defined_in_other_src(node, other_graphs)
        node_dict = graph.nodes[node]
        nest_level = node_dict['nest_level']
        src_line = node_dict['src_line']
        label, color, shape = choose_node_format(
            node, nest_level, src_line,
            defined_somewhere,
            for_latex, multi_page)
        g.add_node(
            node, label=label, color=color, shape=shape)
    # annotate edges
    for u, v in graph.edges():
        g.add_edge(u, v)
    return g


def write_graph2dot(graph, other_graphs, c_fname, img_fname,
                    for_latex, multi_page, layout):
    if pydot is None:
        print('Pydot not found. Exporting using pycflow2dot.write_dot_file().')
        dot_str = dump_dot_wo_pydot(
            graph, other_graphs, c_fname,
            for_latex=for_latex, multi_page=multi_page)
        dot_path = write_dot_file(dot_str, img_fname)
    else:
        # dump using networkx and pydot
        g = _annotate_graph(
            graph, other_graphs, c_fname, for_latex, multi_page)
        dot_path = _dump_graph_to_dot(g, img_fname, layout)
    return dot_path


def _set_pydot_layout(pydot_graph, layout):
    pydot_graph.set_splines('true')
    if layout == 'twopi':
        pydot_graph.set_ranksep(5)
        pydot_graph.set_root('main')
    else:
        pydot_graph.set_overlap(False)
        pydot_graph.set_rankdir('LR')


def write_graphs2dot(graphs, c_fnames, img_fname, for_latex, multi_page, layout):
    dot_paths = list()
    for counter, (graph, c_fname) in enumerate(zip(graphs, c_fnames)):
        other_graphs = list(graphs)
        other_graphs.remove(graph)
        cur_img_fname = img_fname + str(counter)
        dot_path = write_graph2dot(
            graph, other_graphs, c_fname, cur_img_fname,
            for_latex, multi_page, layout)
        dot_paths.append(dot_path)
    return dot_paths


def _dump_graph_to_dot(graph, img_fname, layout):
    """Dump `graph` to `dot` file with base `img_fname`."""
    pydot_graph = nx.drawing.nx_pydot.to_pydot(graph)
    _set_pydot_layout(pydot_graph, layout)
    dot_path = img_fname + '.dot'
    pydot_graph.write(dot_path, format='dot')
    return dot_path


def check_cflow_dot_availability():
    required = ['cflow', 'dot']
    dep_paths = list()
    for dependency in required:
        path = subprocess.check_output(['which', dependency])
        path = bytes2str(path)
        if path.find(dependency) < 0:
            raise Exception(dependency + ' not found in $PATH.')
        path = path.replace('\n', '')
        print('found {dependency} at: {path}'.format(
            dependency=dependency, path=path))
        dep_paths.append(path)
    return dep_paths


def dot2img(dot_paths, img_format, layout):
    print('This may take some time... ...')
    for dot_path in dot_paths:
        img_fname = str(dot_path)
        img_fname = img_fname.replace('.dot', '.' + img_format)
        dot_cmd = [layout, '-T' + img_format, '-o', img_fname, dot_path]
        logger.debug(dot_cmd)
        subprocess.check_call(dot_cmd)
    print(img_format + ' produced successfully from dot.')


def latex_preamble_str():
    """Return string for LaTeX preamble.

    Used if you want to compile the SVGs stand-alone.

    If SVGs are included as part of LaTeX document, then copy required
    packages from this example to your own preamble.
    """
    latex = r"""
    \documentclass[12pt, final]{article}

    usepackage{mybasepreamble}
    % fix this !!! to become a minimal example

    \usepackage[paperwidth=25.5in, paperheight=28.5in]{geometry}

    \newcounter{desccount}
    \newcommand{\descitem}[1]{%
        	\refstepcounter{desccount}\label{#1}
    }
    \newcommand{\descref}[2][\undefined]{%
    	\ifx#1\undefined%
        \hyperref[#2]{#2}%
    	\else%
    	    \hyperref[#2]{#1}%
    	\fi%
    }%
    """
    return latex


def write_latex():
    latex_str = latex_preamble_str()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-filenames', nargs='+',
                        help='filename(s) of C source code files to be parsed.')
    parser.add_argument('-o', '--output-filename', default='cflow',
                        help='name of dot, svg, pdf etc file produced')
    parser.add_argument('-f', '--output-format', default='svg',
                        choices=['dot', 'svg', 'pdf', 'png'],
                        help='output file format')
    parser.add_argument('-l', '--latex-svg', default=False, action='store_true',
                        help='produce SVG for import to LaTeX via Inkscape')
    parser.add_argument('-m', '--multi-page', default=False, action='store_true',
                        help='produce hyperref links between function calls '
                              + 'and their definitions. Used for multi-page '
                              + 'PDF output, where each page is a different '
                              + 'source file.')
    parser.add_argument('-p', '--preprocess', default=False, nargs='?',
                        help='pass --cpp option to cflow, '
                        + 'invoking C preprocessor, optionally with args.')
    parser.add_argument('-r', '--reverse', default=False, action='store_true',
                        help='pass --reverse option to cflow, '
                        + 'chart callee-caller dependencies')
    parser.add_argument(
        '-g', '--layout', default='dot',
        choices=['dot', 'neato', 'twopi', 'circo', 'fdp', 'sfdp'],
        help='graphviz layout algorithm.')
    parser.add_argument(
        '-x', '--exclude', default='',
        help='file listing functions to ignore')
    parser.add_argument(
        '-v', '--verbosity', default='ERROR',
        choices=['ERROR', 'WARNING', 'INFO', 'DEBUG'],
        help='logging level')
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    return args


def rm_excluded_funcs(list_fname, graphs):
    # nothing ignored ?
    if not list_fname:
        return
    # load list of ignored functions
    rm_nodes = [line.strip() for line in open(list_fname).readlines()]
    # delete them
    for graph in graphs:
        for node in rm_nodes:
            if node in graph:
                graph.remove_node(node)


def main():
    """Run cflow, parse output, produce dot and compile it into pdf | svg."""
    copyright_msg = 'cflow2dot'
    print(copyright_msg)
    # input
    cflow, dot = check_cflow_dot_availability()
    # parse arguments
    args = parse_args()
    c_fnames = args.input_filenames
    img_format = args.output_format
    for_latex = args.latex_svg
    multi_page = args.multi_page
    img_fname = args.output_filename
    preproc = args.preprocess
    do_rev = args.reverse
    layout = args.layout
    exclude_list_fname = args.exclude
    # configure the logger
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(args.verbosity)
    logger.info((
        'C source files:\n\t{c_fnames},\n'
        'img fname:\n\t{img_fname}.{img_format}\n'
        'LaTeX export from Inkscape:\n\t{for_latex}\n'
        'Multi-page PDF:\n\t{multi_page}').format(
            c_fnames=c_fnames,
            img_fname=img_fname,
            img_format=img_format,
            for_latex=for_latex,
            multi_page=multi_page))
    cflow_strs = list()
    for c_fname in c_fnames:
        cur_str = call_cflow(
            c_fname, cflow, numbered_nesting=True,
            preprocess=preproc, do_reverse=do_rev)
        cflow_strs.append(cur_str)
    # parse `cflow` output
    graphs = list()
    for cflow_out, c_fname in zip(cflow_strs, c_fnames):
        cur_graph = cflow2nx(cflow_out, c_fname)
        graphs.append(cur_graph)
    rm_excluded_funcs(exclude_list_fname, graphs)
    dot_paths = write_graphs2dot(
        graphs, c_fnames, img_fname, for_latex,
        multi_page, layout)
    dot2img(dot_paths, img_format, layout)


if __name__ == "__main__":
    main()
