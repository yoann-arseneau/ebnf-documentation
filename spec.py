import io
import pytomlpp as toml
import railroad as rr
import ebnf
import jinja2
from markdown import markdown

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

	env = jinja2.Environment(loader = jinja2.FileSystemLoader('.'))
	env.filters.update(
		railroad = syntaxToRailroad,
		ebnf = syntaxToEbnf,
		markdown = markdown)

	spec = toml.load(opts.input)
	if opts.input.close:
		opts.input.close()
	rules = spec["rules"]
	for i in range(len(rules)):
		rule = rules[i]
		if "syntax" in rule:
			rule["syntax"] = ebnf.Reader(rule["syntax"]).read()
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
def toRailroad(node):
	if isinstance(node, ebnf.Alternation):
		return rr.Choice(0, *(toRailroad(x) for x in node.items))
	elif isinstance(node, ebnf.Sequence):
		return rr.Sequence(*(toRailroad(x) for x in node.items))
	elif isinstance(node, ebnf.Optional):
		return rr.Optional(toRailroad(node.item))
	elif isinstance(node, ebnf.ZeroOrMore):
		return rr.ZeroOrMore(toRailroad(node.item))
	elif isinstance(node, ebnf.OneOrMore):
		return rr.OneOrMore(toRailroad(node.item))
	elif isinstance(node, ebnf.Terminal):
		return rr.Terminal(node.text, cls=node.cls)
	elif isinstance(node, ebnf.NonTerminal):
		return rr.NonTerminal(node.text, href=f"#rule-{node.text}")
	else:
		raise ValueError("unexpected value: " + str(node))

def syntaxToEbnf(node, prefix='', sep='\n'):
	if isinstance(node, str):
		node = ebnf.Reader(node).read()
	buf = io.StringIO()
	if isinstance(node, ebnf.Alternation):
		buf.write(f'{prefix}::= ')
		buf.write(toEbnf(node.items[0], False))
		for i in range(1, len(node.items)):
			buf.write(f'{sep}{prefix}  | ')
			buf.write(toEbnf(node.items[i], False))
	else:
		buf.write(f'{prefix}::= ')
		buf.write(toEbnf(node, False))
	return buf.getvalue()
def toEbnf(node, brace):
	if isinstance(node, ebnf.Alternation):
		text = ' | '.join((toEbnf(x, False) for x in node.items))
		if brace:
			text = f'({text})'
		return text
	elif isinstance(node, ebnf.Sequence):
		text = ' '.join((toEbnf(x, False) for x in node.items))
		if brace:
			text = f'({text})'
		return text
	elif isinstance(node, ebnf.Optional):
		return f'{toEbnf(node.item, True)}?'
	elif isinstance(node, ebnf.ZeroOrMore):
		return f'{toEbnf(node.item, True)}*'
	elif isinstance(node, ebnf.OneOrMore):
		return f'{toEbnf(node.item, True)}+'
	elif isinstance(node, (ebnf.Terminal, ebnf.NonTerminal)):
		return node.text
	else:
		raise ValueError("unexpected value: " + str(node))

if __name__ == "__main__":
	main()

