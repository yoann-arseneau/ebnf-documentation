import io
import pytomlpp as toml
import railroad as rr
import ebnf
import jinja2
from markdown import markdown

def renderRailroad(x):
	buf = io.StringIO()
	ebnf.renderRailroad(x, buf.write, css=None)
	return buf.getvalue()
def renderEbnf(x):
	buf = io.StringIO()
	ebnf.renderEbnf(x, buf.write)
	return buf.getvalue()

env = jinja2.Environment(loader = jinja2.FileSystemLoader('.'))
env.filters.update(
	railroad = renderRailroad,
	ebnf = renderEbnf,
	markdown = markdown)
with open('spec.toml') as f: spec=toml.load(f)
env.get_template('body.html').stream(**spec).dump('output.html')

