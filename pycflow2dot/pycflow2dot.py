# -*- coding: utf-8 -*-
"""Plot `cflow` output as graphs."""
# Copyright 2013-2020 Ioannis Filippidis
# Copyright 2010 unknown developer:  https://code.google.com/p/cflow2dot/
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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
from __future__ import absolute_import
import argparse
import locale
import logging
import os
import re
import subprocess
import sys

import networkx as nx
try:
    import pydot
except:
    pydot = None

from pycflow2dot import __version__ as _VERSION


_COLORS = ['#eecc80', '#ccee80', '#80ccee', '#eecc80', '#80eecc']
_DOT_RESERVED = {'graph', 'strict', 'digraph', 'subgraph', 'node', 'edge'}
logger = logging.getLogger(__name__)


def bytes2str(b):
    encoding = locale.getdefaultlocale()[1]
    return b.decode(encoding)


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


def cflow2nx(cflow_str, c_fname):
    """Return graph from output of `cflow`.

    @param cflow_str: output of `cflow`
    @type cflow_str: `str`
    @param c_fname: name of C file
    @type c_fname: `str`
    @return: graph of nodes named after functions,
        with attributes:
        - `nest_level`: distance of call from root
        - `src_line`: source line number or
            `-1` if function is defined in another file
    @rtype: `networkx.DiGraph`
    """
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
        logger.debug(
            f'Found function:\n\t{func_name}'
            f',\n at depth:\n\t{nest_level}'
            f',\n at src line:\n\t{src_line_no}')
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
                f'Found edge:\n\t{pred_node}--->{cur_node}')
    return g


def rename_if_reserved_by_dot(word):
    # dot is case-insensitive, according to:
    #   https://www.graphviz.org/doc/info/lang.html
    if word.lower() in _DOT_RESERVED:
        word = word + '_'
    return word


def dot_preamble(c_fname, for_latex, rankdir):
    c_fname = _graph_name_for_latex(c_fname, for_latex)
    d = _graph_node_defaults()
    node_defaults = ', '.join(
        f'{k}={v}' for k, v in d.items())
    dot_str = (
        'digraph G {\n'
        f'node [{node_defaults}];\n'
        f'rankdir={rankdir};\n'
        f'label="{c_fname}"\n')
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
        peripheries='1', style='"filled,rounded"',
        fontname='"Vera Sans Mono"', fillcolor='"#ffffff"')


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
    if src_line == -1:
        color = None
    # fix underscores ?
    label = _escape_underscores(node, for_latex)
    logger.debug('Label:\n\t: ' + label)
    # src line of def here ?
    if src_line != -1:
        if for_latex:
            label = f'{label}\\n{src_line}'
        else:
            label = f'{label}\\n{src_line}'
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
    if color is None or color == '#ffffff':
        dot_str = f'{node}[label="{label}" shape={shape}];\n\n'
    else:
        dot_str = (
            f'{node}[label="{label}" '
            f'fillcolor="{color}" shape={shape}];\n\n')
    return dot_str


def dot_format_edge(from_node, to_node, color):
    dot_str = (
        f'edge [color="{color}"];\n\n'
        f'{from_node}->{to_node}\n')
    return dot_str


def node_defined_in_other_src(node, other_graphs):
    defined_somewhere = False
    for graph in other_graphs:
        if node in graph:
            src_line = graph.nodes[node]['src_line']

            if src_line != -1:
                defined_somewhere = True
    return defined_somewhere


def dump_dot_wo_pydot(
        graph, other_graphs, c_fname,
        for_latex, multi_page, rankdir):
    dot_str = dot_preamble(c_fname, for_latex, rankdir)
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


def _dump_dot_file(dot_str, dot_fname):
    """Dump `dot_str` to `dot` file `dot_fname`."""
    dot_path = dot_fname + '.dot'
    with open(dot_path, 'w') as f:
        f.write(dot_str)
    logger.info('Dumped dot file.')
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
        if color is None or color == '#ffffff':
            attr = dict(label=label, shape=shape)
        else:
            attr = dict(
                label=label,
                shape=shape,
                fillcolor=color,
                peripheries='0')
        g.add_node(node, **attr)
    # annotate edges
    for u, v in graph.edges():
        g.add_edge(u, v)
    return g


def write_graph2dot(graph, other_graphs, c_fname, img_fname,
                    for_latex, multi_page, layout, rankdir):
    if pydot is None:
        print('Pydot not found. Exporting using native exporter.')
        dot_str = dump_dot_wo_pydot(
            graph, other_graphs, c_fname,
            for_latex=for_latex, multi_page=multi_page,
            rankdir=rankdir)
        dot_path = _dump_dot_file(dot_str, img_fname)
    else:
        # dump using networkx and pydot
        g = _annotate_graph(
            graph, other_graphs, c_fname, for_latex, multi_page)
        dot_path = _dump_graph_to_dot(g, img_fname, layout, rankdir)
    return dot_path


def _set_pydot_layout(pydot_graph, layout, rankdir):
    pydot_graph.set_splines('true')
    if layout == 'twopi':
        pydot_graph.set_ranksep(5)
        pydot_graph.set_root('main')
    else:
        pydot_graph.set_overlap(False)
        pydot_graph.set_rankdir(rankdir)


def write_graphs2dot(
        graphs, c_fnames, img_fname,
        for_latex, multi_page, layout, rankdir):
    dot_paths = list()
    for counter, (graph, c_fname) in enumerate(zip(graphs, c_fnames)):
        other_graphs = list(graphs)
        other_graphs.remove(graph)
        cur_img_fname = img_fname + str(counter)
        dot_path = write_graph2dot(
            graph, other_graphs, c_fname, cur_img_fname,
            for_latex, multi_page, layout, rankdir)
        dot_paths.append(dot_path)
    return dot_paths


def _merge_graphs(graphs, c_fnames):
    """Compose graphs from multiple C files into a single graph."""
    g = nx.compose_all(graphs)
    for graph, c_fname in zip(graphs, c_fnames):
        _annotate_nodes_with_filename(g, graph, c_fname)
    return g


def _annotate_nodes_with_filename(g, graph, c_fname):
    """Copy file names to node attributes of `g`.

    For each node `u` of `graph`, if the node `u` is
    defined in file `c_fname`, then annotate the node `u`
    in graph `g` with `c_fname`.

    This function adds the attribute `file_name` to
    all nodes in `g`.
    """
    for u, d in graph.nodes(data=True):
        assert u in g, (u, g.nodes())
        src_line_no = d['src_line']
        if src_line_no == -1:
            continue
        dg = g.nodes[u]
        # assert each function is defined in
        # at most one file
        assert 'file_name' not in dg, dg
        dg['file_name'] = c_fname


def _mark_call_paths(graph, source, target):
    if source is None or target is None:
        return
    source_node = rename_if_reserved_by_dot(source)
    target_node = rename_if_reserved_by_dot(target)
    assert source_node in graph, source_node
    assert target_node in graph, target_node
    for path in nx.all_simple_paths(
            graph, source_node, target_node):
        for u, v in zip(path[:-1], path[1:]):
            graph.edges[u, v]['style'] = '"dashed"'


def _format_merged_graph(graph, for_latex):
    """Return graph with `dot` labeling."""
    g = nx.DiGraph()
    g.graph['node'] = _graph_node_defaults()
    c_fnames = _collect_file_names(graph)
    colormap = _make_colormap(c_fnames)
    shape = '"ellipse"'
    for u, d in graph.nodes(data=True):
        _format_merged_node(
            u, d, g, for_latex, shape, colormap)
    for u, v, d in graph.edges(data=True):
        g.add_edge(u, v, **d)
    return g


def _collect_file_names(graph):
    """Return `set` of values of node attribute `file_name`."""
    c_fnames = set()
    for u, d in graph.nodes(data=True):
        c_fname = d.get('file_name')
        if c_fname is None:
            continue
        c_fnames.add(c_fname)
    return c_fnames


def _make_colormap(c_fnames):
    """Return `dict` that maps `c_fnames` to colors."""
    colormap = dict()
    n = len(_COLORS)
    for i, fname in enumerate(c_fnames):
        colormap[fname] = _COLORS[i % n]
    return colormap


def _format_merged_node(u, d, g, for_latex, shape, colormap):
    """Add node `u` to `g` forming label using `d`."""
    src_line = d['src_line']
    file_name = d.get('file_name')
    node_name = _escape_underscores(u, for_latex)
    if file_name is None:
        assert src_line == -1, src_line
        label = f'{node_name}\\n'
        attr = dict(label=label, shape=shape)
    else:
        label = (
            f'{node_name}\\n'
            f'{file_name}\\n'
            f'{src_line}\\n')
        fillcolor = colormap[file_name]
        attr = dict(
            label=label,
            shape=shape,
            fillcolor=fillcolor,
            peripheries='0')
    g.add_node(u, **attr)


def _dump_graph_to_dot(graph, img_fname, layout, rankdir):
    """Dump `graph` to `dot` file with base `img_fname`."""
    pydot_graph = nx.drawing.nx_pydot.to_pydot(graph)
    _set_pydot_layout(pydot_graph, layout, rankdir)
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
        print(f'found {dependency} at: {path}')
        dep_paths.append(path)
    return dep_paths


def dot2img(dot_paths, img_format, layout):
    print('This may take some time... ...')
    for dot_path in dot_paths:
        root, ext = os.path.splitext(dot_path)
        assert ext == '.dot', ext
        img_fname = f'{root}.{img_format}'
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
    parser.add_argument('--merge', default=False, action='store_true',
                        help='create a single graph for multiple C files.')
    parser.add_argument(
        '--source', action='store',
        help=('start node for call path highlighting. '
            'Available only with option `--merge`.'))
    parser.add_argument(
        '--target', action='store',
        help=('end node for call path highlighting'
            'Available only with option `--merge`.'))
    parser.add_argument(
        '-g', '--layout', default='dot',
        choices=['dot', 'neato', 'twopi', 'circo', 'fdp', 'sfdp'],
        help='graphviz layout algorithm.')
    parser.add_argument(
        '--rankdir', default='LR',
        choices=['TB', 'LR', 'BT', 'RL'],
        help='graph layout direction given to `dot`.')
    parser.add_argument(
        '-x', '--exclude', default='',
        help='file listing functions to ignore; combined with --exclude-functions')
    parser.add_argument(
        '-X', '--exclude-functions', default='',
        help='functions to ignore; combined with --exclude')
    parser.add_argument(
        '-v', '--verbosity', default='ERROR',
        choices=['ERROR', 'WARNING', 'INFO', 'DEBUG'],
        help='logging level')
    parser.add_argument(
        '--version', action='version',
        version=f'cflow2dot version {_VERSION}')
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    return args


def _parse_excluded_funcs(list_fname, func_names):
    out = set()
    func_names = re.split(r'[;, ]+', func_names)
    out.update(func_names)
    if list_fname:
        with open(list_fname, 'r') as file:
            out.update(line.strip() for line in file)
    return out


def rm_excluded_funcs(rm_nodes, graphs):
    # delete them
    for graph in graphs:
        for node in rm_nodes:
            if node in graph:
                graph.remove_node(node)


def main():
    """Run cflow, parse output, produce dot and compile it into pdf | svg."""
    # parse arguments
    args = parse_args()
    c_fnames = args.input_filenames
    img_format = args.output_format
    for_latex = args.latex_svg
    multi_page = args.multi_page
    img_fname = args.output_filename
    preproc = args.preprocess
    do_rev = args.reverse
    merge = args.merge
    source = args.source
    target = args.target
    layout = args.layout
    rankdir = args.rankdir
    exclude_list_fname = args.exclude
    exclude_arg_funcs = args.exclude_funcs
    # configure the logger
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(args.verbosity)
    logger.info(
        f'C source files:\n\t{c_fnames},\n'
        f'img fname:\n\t{img_fname}.{img_format}\n'
        f'LaTeX export from Inkscape:\n\t{for_latex}\n'
        f'Multi-page PDF:\n\t{multi_page}')
    print('cflow2dot')
    # input
    cflow, dot = check_cflow_dot_availability()
    # call `cflow`
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
    exclude_list = _parse_excluded_funcs(exclude_list_fname, exclude_arg_funcs)
    rm_excluded_funcs(exclude_list, graphs)
    if merge:
        g = _merge_graphs(graphs, c_fnames)
        _mark_call_paths(g, source, target)
        g = _format_merged_graph(g, for_latex)
        dot_path = _dump_graph_to_dot(g, img_fname, layout, rankdir)
        dot_paths = [dot_path]
    else:
        dot_paths = write_graphs2dot(
            graphs, c_fnames, img_fname, for_latex,
            multi_page, layout, rankdir)
    dot2img(dot_paths, img_format, layout)


if __name__ == "__main__":
    main()
