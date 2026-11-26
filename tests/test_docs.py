"""Checks of the documentation in docs/: both languages have the same pages, the links between pages resolve,
and the example config of the user guide builds. Run: uv run pytest"""

import json
import os
import re
import tempfile

from asfinger import Model

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'docs')
LANGS = ('en', 'zh')


def pages(lang):
    out = []
    for d, _, files in os.walk(os.path.join(DOCS, lang)):
        out += [os.path.relpath(os.path.join(d, f), os.path.join(DOCS, lang)) for f in files if f.endswith('.md')]
    return sorted(out)


def slug(heading):
    """The anchor that the site and GitHub give a heading."""
    s = re.sub(r'[`*_]', '', heading).strip().lower()
    s = re.sub(r'[^\w\- ]', '', s)
    return s.replace(' ', '-')


def anchors(path):
    with open(path, encoding='utf-8') as f:
        text = re.sub(r'```.*?```', '', f.read(), flags=re.S)
    return {slug(m) for m in re.findall(r'^#{1,6}\s+(.+?)\s*$', text, re.M)}


def test_same_pages_in_both_languages():
    assert pages('en') == pages('zh')
    assert {'index.md', 'glossary.md'} <= set(pages('en'))
    for section in ('user', 'developer', 'agents'):
        assert os.path.join(section, 'index.md') in pages('en'), section


def test_every_page_has_one_title():
    for lang in LANGS:
        for rel in pages(lang):
            with open(os.path.join(DOCS, lang, rel), encoding='utf-8') as f:
                text = re.sub(r'```.*?```', '', f.read(), flags=re.S)
            assert text.startswith('# '), f'{lang}/{rel} must start with "# Title"'
            assert len(re.findall(r'^# ', text, re.M)) == 1, f'{lang}/{rel} has more than one "# " heading'


def test_links_between_pages_resolve():
    for lang in LANGS:
        for rel in pages(lang):
            path = os.path.join(DOCS, lang, rel)
            with open(path, encoding='utf-8') as f:
                text = re.sub(r'```.*?```', '', f.read(), flags=re.S)
            for href in re.findall(r'\]\(([^)\s]+)\)', text):
                if re.match(r'[a-z]+:', href):
                    continue
                target, _, anchor = href.partition('#')
                dest = os.path.normpath(os.path.join(os.path.dirname(path), target)) if target else path
                assert os.path.isfile(dest), f'{lang}/{rel}: broken link {href}'
                if anchor and dest.endswith('.md'):
                    assert anchor in anchors(dest), f'{lang}/{rel}: no heading for {href}'


def example_config(lang):
    with open(os.path.join(DOCS, lang, 'user', 'config-file.md'), encoding='utf-8') as f:
        blocks = re.findall(r'```json\n(.*?)```', f.read(), flags=re.S)
    whole = [b for b in blocks if b.lstrip().startswith('{') and '"minimal_rod"' in b]
    assert len(whole) == 1, 'the page must hold exactly one complete example config'
    return whole[0]


def test_example_config_of_the_user_guide_builds():
    assert example_config('en') == example_config('zh')
    cfg = json.loads(example_config('en'))
    m = Model(cfg, tempfile.mkdtemp())
    m.log = lambda *a: None
    out = tempfile.mkdtemp()
    R, rep = m.build(out)
    assert m.check(R) == [] and rep['interference'] == []
    assert rep['parts']['rod']['mass_g'] == 46.8  # the number the page quotes
    for f in ('print/rod.stl', 'meshes/rod.stl', 'ipush_tool.xml', 'preview.html', 'resolved.json', 'report.json'):
        assert os.path.isfile(os.path.join(out, f)), f
    tilted = Model(cfg, '.').set(rod_tilt=70)
    assert len(tilted.check()) == 1  # the check that the page shows failing
