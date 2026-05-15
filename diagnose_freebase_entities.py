import argparse
import gzip
from collections import Counter

NS_PREFIX = b"<http://rdf.freebase.com/ns/"
NAME_PRED = b"<http://rdf.freebase.com/ns/type.object.name>"


def parse_literal(obj):
    if not obj.startswith(b'"'):
        return None, None

    i = 1
    escaped = False
    while i < len(obj):
        c = obj[i]
        if escaped:
            escaped = False
        elif c == 92:
            escaped = True
        elif c == 34:
            break
        i += 1

    if i >= len(obj):
        return None, None

    return obj[1:i], obj[i + 1 :]


def load_ids(path):
    ids = []
    malformed = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            entity_id = raw.strip()
            if not entity_id:
                continue
            ids.append(entity_id)
            if not (entity_id.startswith("m.") or entity_id.startswith("g.")):
                malformed.append((lineno, entity_id))
    return ids, malformed


def normalize_object(obj):
    obj = obj.rstrip()
    if obj.endswith(b"."):
        obj = obj[:-1].rstrip()
    return obj


def analyze(input_file, ids, max_lines=None, sample_limit=20):
    missing = {entity_id.encode() for entity_id in ids}

    seen_subject = set()
    seen_object = set()
    extractable = set()

    subject_rows = 0
    object_rows = 0
    extractable_rows = 0
    reasons = Counter()

    with gzip.open(input_file, "rb") as fin:
        for line_no, line in enumerate(fin, 1):
            if max_lines and line_no > max_lines:
                break

            if not line.startswith(NS_PREFIX):
                continue

            parts = line.strip().split(None, 2)
            if len(parts) < 3:
                reasons["short_line"] += 1
                continue

            subj, pred, obj = parts
            sid = subj[len(NS_PREFIX):-1]
            obj = normalize_object(obj)

            if sid in missing:
                seen_subject.add(sid)
                subject_rows += 1

                if not pred.startswith(NS_PREFIX):
                    reasons["pred_not_freebase_ns"] += 1
                else:
                    value = None

                    if obj.startswith(NS_PREFIX) and obj.endswith(b">"):
                        value = obj[len(NS_PREFIX):-1]
                    elif obj.startswith(b'"'):
                        literal, rest = parse_literal(obj)
                        if literal is None:
                            reasons["literal_parse_fail"] += 1
                        else:
                            if pred == NAME_PRED and not rest.startswith(b"@en"):
                                reasons["name_not_en"] += 1
                            else:
                                value = literal
                    else:
                        reasons["object_not_uri_or_literal"] += 1

                    if value is not None:
                        try:
                            sid.decode()
                            pred[len(NS_PREFIX):-1].decode()
                            value.decode()
                        except UnicodeDecodeError:
                            reasons["unicode_decode_error"] += 1
                        else:
                            extractable.add(sid)
                            extractable_rows += 1

            if obj.startswith(NS_PREFIX) and obj.endswith(b">"):
                oid = obj[len(NS_PREFIX):-1]
                if oid in missing:
                    seen_object.add(oid)
                    object_rows += 1

    return {
        "line_limit": max_lines,
        "missing_total": len(missing),
        "subject_hit_ids": len(seen_subject),
        "subject_hit_rows": subject_rows,
        "object_hit_ids": len(seen_object),
        "object_hit_rows": object_rows,
        "extractable_ids": len(extractable),
        "extractable_rows": extractable_rows,
        "drop_reasons": dict(reasons.most_common()),
        "sample_subject_only": sorted((seen_subject - seen_object))[:sample_limit],
        "sample_object_only": sorted((seen_object - seen_subject))[:sample_limit],
        "sample_no_hits": sorted((missing - seen_subject - seen_object))[:sample_limit],
        "sample_seen_but_not_extractable": sorted((seen_subject - extractable))[:sample_limit],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="freebase-rdf-latest.gz")
    parser.add_argument("--ids", default="missing_entities2.txt")
    parser.add_argument("--max-lines", type=int, default=None)
    parser.add_argument("--sample-limit", type=int, default=20)
    args = parser.parse_args()

    ids, malformed = load_ids(args.ids)
    report = analyze(
        input_file=args.input,
        ids=ids,
        max_lines=args.max_lines,
        sample_limit=args.sample_limit,
    )

    print("ids_file:", args.ids)
    print("input_file:", args.input)
    print("malformed_ids:", len(malformed))
    for lineno, entity_id in malformed[: args.sample_limit]:
        print(f"  malformed line {lineno}: {entity_id}")

    for key, value in report.items():
        if isinstance(value, list):
            decoded = [item.decode() if isinstance(item, bytes) else item for item in value]
            print(f"{key}:")
            for item in decoded:
                print(f"  {item}")
        else:
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
