import io
from functools import partial
import pytomlpp as toml
import railroad as rr
import syntax
import jinja2
import markdown

def main():
	import sys, argparse
	parser = argparse.ArgumentParser(
		description = "Generates documentation for a formal syntax.",
		epilog = "created by Yoann Arseneau")
	parser.add_argument('template')
	parser.add_argument(
		'-i', '--input',
		help = "the definition file",
		type = argparse.FileType('r'),
		default = sys.stdin)
	parser.add_argument(
		'-o', '--output',
		help = "the output file",
		type = argparse.FileType('w'),
		default = sys.stdout)
	opts = parser.parse_args(sys.argv[1:])

	mdContext = markdown.Markdown(
		extensions = ['fenced_code', 'codehilite'],
		extension_configs = { 'codehilite': { 'noclasses': True } })

	env = jinja2.Environment(loader = jinja2.FileSystemLoader('.'))
	env.filters.update(
		railroad = syntaxToRailroad,
		ebnf = syntaxToEbnf,
		markdown = mdContext.convert)

	spec = toml.load(opts.input)
	if opts.input.close:
		opts.input.close()
	rules = spec["rules"]
	for i in range(len(rules)):
		rule = rules[i]
		if "syntax" in rule:
			rule["syntax"] = syntax.Reader(rule["syntax"]).read()
		if "label" not in rule:
			rule["label"] = rule.get("name")
	env.get_template(opts.template).stream(**spec).dump(opts.output)
	if opts.output.close:
		opts.output.close()

def syntaxToRailroad(node):
	if isinstance(node, str):
		node = ebnf.Reader(node).read()
	buf = io.StringIO()
	rr.Diagram(toRailroad(node), css=None).writeSvg(buf.write)
	return buf.getvalue()
def syn2rr_container(ctor):
	return lambda node: ctor(*(toRailroad(x) for x in node.items))
def syn2rr_node(ctor):
	return lambda node: ctor(toRailroad(node.item))
syn2rr_lookup = {
	syntax.Alternation: syn2rr_container(partial(rr.Choice, 0)),
	syntax.Sequence: syn2rr_container(rr.Sequence),
	syntax.Optional: syn2rr_node(rr.Optional),
	syntax.ZeroOrMore: syn2rr_node(rr.ZeroOrMore),
	syntax.OneOrMore: syn2rr_node(rr.OneOrMore),
	syntax.Terminal: lambda x: rr.Terminal(x.text, cls=x.cls),
	syntax.NonTerminal: lambda x: rr.NonTerminal(x.text, href=f'#rule-{x.text}'),
}
def toRailroad(node):
	try:
		return syn2rr_lookup[type(node)](node)
	except KeyError:
		raise ValueError(f'unexpected type {type(node)}')

def syntaxToEbnf(node, prefix='', sep='\n'):
	if isinstance(node, str):
		node = ebnf.Reader(node).read()
	buf = io.StringIO()
	if isinstance(node, syntax.Alternation):
		buf.write(f'{prefix}::= ')
		buf.write(toEbnf(node.items[0], False))
		for i in range(1, len(node.items)):
			buf.write(f'{sep}{prefix}  | ')
			buf.write(toEbnf(node.items[i], False))
	else:
		buf.write(f'{prefix}::= ')
		buf.write(toEbnf(node, False))
	return buf.getvalue()
def syn2ebnf_container(sep, itemBrace):
	def t(node, brace):
		text = sep.join(toEbnf(x, itemBrace) for x in node.items)
		return f'({text})' if brace else text
	return t
def syn2ebnf_quantifier(symbol):
	return lambda node, _: toEbnf(node.item, True) + symbol
syn2ebnf_lookup = {
	syntax.Alternation: syn2ebnf_container(' | ', False),
	syntax.Sequence: syn2ebnf_container(' ', True),
	syntax.Optional: syn2ebnf_quantifier('?'),
	syntax.ZeroOrMore: syn2ebnf_quantifier('*'),
	syntax.OneOrMore: syn2ebnf_quantifier('+'),
	syntax.Terminal: lambda x, _: x.text,
	syntax.NonTerminal: lambda x, _: x.text,
}
def toEbnf(node, brace):
	try:
		return syn2ebnf_lookup[type(node)](node, brace)
	except KeyError:
		raise ValueError(f'unexpected type {type(node)}')

if __name__ == "__main__":
	main()

