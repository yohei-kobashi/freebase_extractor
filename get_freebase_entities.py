import json
import gzip

NS_PREFIX = b"<http://rdf.freebase.com/ns/"
NAME_PRED = b"<http://rdf.freebase.com/ns/type.object.name>"


def open_file(path):
    f = open(path, "rb", buffering=16 * 1024 * 1024)
    if f.read(2) == b"\x1f\x8b":
        f.seek(0)
        return gzip.open(f, "rb")
    f.seek(0)
    return f


def parse_literal(obj):
    """
    Extract literal content from
    "..."
    "... "@en
    "... "@xx
    "... "^^<...>
    """
    if not obj.startswith(b'"'):
        return None, None

    i = 1
    escaped = False

    while i < len(obj):
        c = obj[i]
        if escaped:
            escaped = False
        elif c == 92:  # \
            escaped = True
        elif c == 34:  # "
            break
        i += 1

    if i >= len(obj):
        return None, None

    literal = obj[1:i]
    rest = obj[i+1:]

    return literal, rest


def normalize_object(obj):
    obj = obj.rstrip()
    if obj.endswith(b"."):
        obj = obj[:-1].rstrip()
    return obj


def extract(input_file, output_file):
    with open("missing_entities2.txt", "rb") as f:
        missing_entities = {row.strip() for row in f}
    with open_file(input_file) as fin, \
         open(output_file, "w", encoding="utf-8", buffering=8 * 1024 * 1024) as fout:

        for line in fin:

            if not line.startswith(NS_PREFIX):
                continue

            parts = line.strip().split(None, 2)
            if len(parts) < 3:
                continue

            subj, pred, obj = parts
            obj = normalize_object(obj)

            if not pred.startswith(NS_PREFIX):
                continue

            sid = subj[len(NS_PREFIX):-1]
            
            if not sid in missing_entities:
                continue

            pid = pred[len(NS_PREFIX):-1]

            value = None

            # case1: object is Freebase URI
            if obj.startswith(NS_PREFIX) and obj.endswith(b">"):
                value = obj[len(NS_PREFIX):-1]

            # case2: literal
            elif obj.startswith(b'"'):
                literal, rest = parse_literal(obj)
                if literal is None:
                    continue

                # type.object.name -> only @en
                if pred == NAME_PRED:
                    if not rest.startswith(b"@en"):
                        continue

                value = literal

            if value is None:
                continue

            try:
                record = {
                    "id": sid.decode(),
                    "property": pid.decode(),
                    "value": value.decode()
                }
            except UnicodeDecodeError:
                continue

            fout.write(json.dumps(record, ensure_ascii=False))
            fout.write("\n")


if __name__ == "__main__":
    extract(
        "freebase-rdf-latest",
        "freebase_triples.jsonl"
    )
