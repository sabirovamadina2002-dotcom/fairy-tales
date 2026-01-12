# relemmatize_spacy.py
import json
import re
from pathlib import Path
import spacy

nlp = spacy.load("ru_core_news_sm")

def parse_title(title_str):
    title = "Без названия"
    collector = None
    translator = None

    parts = [p.strip() for p in title_str.split('.') if p.strip()]
    if parts:
        title = parts[0]

    coll_match = re.search(r'Сказочник\s+(.+?)(?:\.$|\. )', title_str)
    if coll_match:
        collector = coll_match.group(1).strip()

    trans_match = re.search(r'Перевел[а]?\s+(.+?)(?:\.$|\. )', title_str)
    if trans_match:
        translator = trans_match.group(1).strip()

    return title, collector, translator

def clean_content(content):
    content = re.split(r'Social Like', content)[0].strip()
    content = re.sub(r'.*Опубликовано:\s*\d{2}\.\d{2}\.\d{4}', '', content, flags=re.DOTALL).strip()
    return content

def main():
    input_file = Path("data/fairy_tales_linguistic_annotated.json")
    output_file = Path("data/fairy_tales_corrected.json")

    with open(input_file, encoding='utf-8') as f:
        data = json.load(f)

    corrected = []

    for tale in data:
        raw_title = tale.get('title', 'Без названия')
        url = tale.get('url', '').strip()

        title, collector, translator = parse_title(raw_title)
        clean_text = clean_content(tale['content'])

        # === 1. Аннотация для ПОИСКА ===
        flat_text = clean_text.replace('\n', ' ')
        if not flat_text.strip():
            flat_text = "."
        doc_for_search = nlp(flat_text)

        # Извлекаем предложения и токены
        structured_sents = []
        for sent in doc_for_search.sents:
            tokens = []
            for token in sent:
                tokens.append({
                    "form": token.text,
                    "lemma": token.lemma_.lower(),
                    "pos": token.pos_
                })
            structured_sents.append({
                "text": sent.text.strip(),
                "tokens": tokens
            })

        # === 2. ИЗВЛЕЧЕНИЕ ИМЕНОВАННЫХ СУЩНОСТЕЙ (NER) ===
        named_entities = []
        for ent in doc_for_search.ents:
            label = ent.label_.upper()
            if label == "PER" or label == "PERSON":
                ent_type = "per"
            elif label == "LOC" or label == "GPE":
                ent_type = "loc"
            else:
                continue  # пропускаем ORG, MISC и др.
            named_entities.append({
                "text": ent.text,
                "type": ent_type
            })

        # === 3. Сохраняем без html_text ===
        corrected.append({
            "id": url,
            "metadata": {
                "title": title,
                "collector": collector,
                "translator": translator
            },
            "sentences": structured_sents,
            "named_entities": named_entities
        })

    # Сохраняем результат
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(corrected, f, ensure_ascii=False, indent=2)

    print("✅ Готово! Файл сохранён:", output_file)

if __name__ == '__main__':
    main()