# app.py
import json
import re
from pathlib import Path
from flask import Flask, render_template, request, abort

app = Flask(__name__)

DATA_DIR = Path("data")
CORRECTED_FILE = DATA_DIR / "fairy_tales_corrected.json"
ENTITIES_FILE = DATA_DIR / "entities_corrected.json"

# Загрузка корпуса
with open(CORRECTED_FILE, encoding='utf-8') as f:
    TALES_LIST = json.load(f)

TALES_BY_URL = {tale["id"].strip(): tale for tale in TALES_LIST}
TOTAL_TALES = len(TALES_BY_URL)

# Загрузка и нормализация сущностей
with open(ENTITIES_FILE, encoding='utf-8') as f:
    ENTITIES_RAW = json.load(f)

ENTITIES = {}
for title_key, data in ENTITIES_RAW.items():
    url_clean = data["url"].strip()
    entities = []
    for ent in data.get("entities", []):
        if isinstance(ent, list) and len(ent) == 2:
            text, raw_type = ent[0], ent[1]
            # Нормализуем типы: PER → per, LOC → loc
            if str(raw_type).upper() == "PER":
                ent_type = "per"
            elif str(raw_type).upper() == "LOC":
                ent_type = "loc"
            else:
                continue  # игнорируем другие типы (ORG, MISC и т.д.)
            entities.append({"text": text, "type": ent_type})
    ENTITIES[url_clean] = entities


def paginate(items, page=1, per_page=10):
    start = (page - 1) * per_page
    return items[start:start + per_page]


@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    paginated_ids = paginate(list(TALES_BY_URL.keys()), page=page, per_page=10)
    paginated_tales = [(tid, TALES_BY_URL[tid]) for tid in paginated_ids]
    return render_template(
        'index.html',
        tales=paginated_tales,
        page=page,
        total=TOTAL_TALES,
        pages=(TOTAL_TALES + 9) // 10
    )


@app.route('/tale/<path:tale_id>')
def tale_view(tale_id):
    tale = TALES_BY_URL.get(tale_id.strip())
    if not tale:
        abort(404)
    return render_template('tale.html', tale=tale)


@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    mode = request.args.get('mode', 'lemma')
    ent_type_filter = request.args.get('ent_type', '').lower()  # ← приводим к нижнему регистру
    results = []
    seen_contexts = set()

    if not query:
        return render_template(
            'search.html',
            results=[],
            query='',
            mode=mode,
            ent_type_filter=ent_type_filter
        )

    if mode == 'lemma':
        q_norm = query.lower()
        for tale in TALES_BY_URL.values():
            for sent in tale['sentences']:
                for token in sent['tokens']:
                    if token.get('lemma', '') == q_norm:
                        if sent['text'] not in seen_contexts:
                            seen_contexts.add(sent['text'])
                            results.append({
                                'tale_id': tale['id'],
                                'title': tale['metadata']['title'],
                                'context': sent['text'],
                                'query': query
                            })
                        break

    elif mode == 'entity':
        q_norm = query.lower()
        for url, entities_here in ENTITIES.items():
            tale = TALES_BY_URL.get(url)
            if not tale:
                continue
            matched_entities = []
            for ent in entities_here:
                if q_norm in ent['text'].lower():
                    # Теперь ent['type'] — всегда 'per' или 'loc'
                    if ent_type_filter and ent['type'] != ent_type_filter:
                        continue
                    matched_entities.append(ent)
            if matched_entities:
                for sent in tale['sentences']:
                    text = sent['text']
                    for ent in matched_entities:
                        if ent['text'] in text and text not in seen_contexts:
                            seen_contexts.add(text)
                            results.append({
                                'tale_id': url,
                                'title': tale['metadata']['title'],
                                'context': text,
                                'entity_type': ent['type'],
                                'entity_text': ent['text']
                            })
                            break

    return render_template(
        'search.html',
        results=results,
        query=query,
        mode=mode,
        ent_type_filter=ent_type_filter
    )


if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)