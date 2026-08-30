import json, glob, os
rows = []
for p in sorted(glob.glob("evaluation/results/*.json")):
    d = json.load(open(p)); m = d["metrics"]
    b = m["true_positives"] + m["false_negatives"]; c = m["true_negatives"] + m["false_positives"]
    rows.append((d["version"], f"{m['true_positives']}/{b}", f"{m['false_positives']}/{c}",
                 f"{m['balanced_accuracy']:.2f}", f"{d['totals']['wall_clock_s']:.0f}s",
                 str(d["totals"]["model_calls"])))
w = [max(len(r[i]) for r in rows + [("config","found","false alarms","score","time","calls")]) for i in range(6)]
hdr = ("config","found","false alarms","score","time","model calls")
print("  " + "  ".join(h.ljust(max(w[i], len(h))) for i, h in enumerate(hdr)))
print("  " + "  ".join("-" * max(w[i], len(h)) for i, h in enumerate(hdr)))
for r in rows:
    print("  " + "  ".join(r[i].ljust(max(w[i], len(hdr[i]))) for i in range(6)))
