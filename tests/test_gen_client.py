import json

from synthguard import gen_client
from synthguard.records import load_yaml


def test_offline_comfy_skips_cleanly(isolated_data, monkeypatch):
    monkeypatch.setenv("COMFY_URL", "http://127.0.0.1:9")  # discard port: nothing listens
    monkeypatch.setenv("SKIP_DIFFUSION", "0")
    st = gen_client.run({"name": "t", "seed_take": 1})
    assert st["status"] == "skipped" and "offline" in st["e1_reason"]
    saved = json.loads((isolated_data / "runs" / "t" / "gen_status.json").read_text())
    assert saved["status"] == "skipped"


def test_skip_flag_short_circuits(isolated_data, monkeypatch):
    monkeypatch.setenv("SKIP_DIFFUSION", "1")
    called = []
    monkeypatch.setattr(gen_client, "probe", lambda *a, **k: called.append(1))
    st = gen_client.run({"name": "t", "seed_take": 1})
    assert st["e1_reason"] == "SKIP_DIFFUSION=1" and not called


def test_workflows_fill_completely():
    cfg = load_yaml("gen_dev_5070")
    for g in [g for g in gen_client.WORKFLOWS if g != "krea2_t2i"]:  # t2i: own test below
        wf = gen_client.fill(gen_client.load_workflow(g),
                             gen_client.build_params(cfg, g, "x.png", 416, 416, 1))
        assert "{{" not in json.dumps(wf)
        sizes = [n["inputs"] for n in wf.values() if n["class_type"] == "ImageScale"][0]
        assert sizes["width"] == 768 and sizes["height"] == 768  # low-VRAM default, not 1024


def test_gen_size_multiple_of_64():
    assert gen_client.gen_size(415, 416, 768) == (768, 768)
    assert gen_client.gen_size(640, 360, 768) == (768, 448)


def test_scene_prompts_cover_all_classes_and_fill():
    import random

    from synthguard.scenes import build_prompt

    spec = load_yaml("scenes_substation")
    rng = random.Random(0)
    seen = set()
    for _ in range(300):
        prompt, picked, (w, h) = build_prompt(spec, rng)
        assert w % 64 == 0 and h % 64 == 0 and len(set(picked)) == len(picked)
        seen |= {c for p in picked for c in spec["elements"][p]["shows"]}
    assert seen == set(spec["classes"])
    for e in spec["elements"].values():
        assert set(e["shows"]) <= set(spec["classes"])
    for prof in ("gen_dev_5070", "gen_deploy_3090"):  # scenes must run on both machines
        w = load_yaml(prof)["weights"]["krea2"]
        wf = gen_client.fill(gen_client.load_workflow("krea2_t2i"),
                             {**w, "width": 1024, "height": 1024, "seed": 1, "steps": 8, "prompt": "x"})
        assert "{{" not in json.dumps(wf)
    # the deploy machine must never let the Krea 2 stand-in produce E1
    assert not load_yaml("gen_deploy_3090").get("fallback_krea2")
