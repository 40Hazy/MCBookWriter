from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import ValidationError

from . import __version__
from .ebook import EbookError
from .llm import (
    DEFAULT_CONFIG_FILE,
    describe_profiles,
    estimate_review,
    load_settings,
    review_job,
    write_report,
)
from .keymanagement import (
    KEY_ENV,
    clear_key,
    key_status,
    save_key,
    source_label,
    test_connection,
)
from .manifest import validate_job, validate_job_data
from .patch import apply_patches, build_unified_diff
from .segment import DEFAULT_MAX_SEGMENT_CHARS
from .workflow import prepare_input


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bookforge")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="导入 txt/epub/azw3/mobi/docx 等并生成 job.json",
    )
    prepare_parser.add_argument("input", type=Path)
    prepare_parser.add_argument("--title", help="书名；省略时使用电子书元数据或文件名")
    prepare_parser.add_argument("--out", type=Path)
    prepare_parser.add_argument("--calibre", help="Calibre ebook-convert 路径")
    prepare_parser.add_argument("--page-limit", type=int, default=100, choices=range(1, 101))
    prepare_parser.add_argument("--max-segment-chars", type=int, default=DEFAULT_MAX_SEGMENT_CHARS)
    prepare_parser.add_argument("--verify", action="store_true", help="打印校验报告")
    prepare_parser.add_argument("--strict", action="store_true", help="有警告时返回非零退出码")

    validate_parser = subparsers.add_parser("validate", help="校验 job.json")
    validate_parser.add_argument("job", type=Path)

    review_parser = subparsers.add_parser("review", help="用 LLM 核验正文并生成报告")
    review_parser.add_argument("job", type=Path)
    review_parser.add_argument("--mode", choices=["report", "patch"], default="report")
    review_parser.add_argument("--out", type=Path)
    review_parser.add_argument("--profile", help="每本书的配置名，默认使用 job 的 titleBase")
    review_parser.add_argument("--key-file", type=Path)
    review_parser.add_argument("--base-url")
    review_parser.add_argument("--model")
    review_parser.add_argument("--timeout", type=float)
    review_parser.add_argument("--max-chars", type=int)
    review_parser.add_argument("--temperature", type=float)
    review_parser.add_argument("--max-tokens", type=int)
    review_parser.add_argument(
        "--thinking",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="启用/禁用推理模式（--thinking / --no-thinking）",
    )
    review_parser.add_argument("--glossary", type=Path)
    pagination = review_parser.add_mutually_exclusive_group()
    pagination.add_argument("--limit", type=int, default=0, help="最多核验的块数，0 表示全部")
    pagination.add_argument("--sample", type=int, default=0, help="从全书均匀抽取 N 块，0 表示关闭")
    review_parser.add_argument(
        "--estimate",
        action="store_true",
        help="只估算块数与 tokens/费用，不调用 API",
    )
    review_parser.add_argument("--strict", action="store_true", help="有问题/错误/拦截时返回非零")

    apply_parser = subparsers.add_parser("apply-patch", help="应用 LLM 补丁并生成新 job")
    apply_parser.add_argument("job", type=Path)
    apply_parser.add_argument("--patch", type=Path, required=True)
    apply_parser.add_argument("--out", type=Path)
    apply_parser.add_argument(
        "--min-confidence",
        choices=["high", "medium", "low"],
        default=None,
        help="默认使用补丁报告中的 policy.minConfidence",
    )
    apply_parser.add_argument("--dry-run", action="store_true")
    apply_parser.add_argument("--strict", action="store_true", help="有补丁被拒绝时返回非零")

    profile_parser = subparsers.add_parser("profile", help="查看 LLM profiles 与 key 状态")
    profile_sub = profile_parser.add_subparsers(dest="profile_command", required=True)
    profile_list = profile_sub.add_parser("list", help="列出全局与每本书 profile")
    profile_list.add_argument("--config", type=Path, help="llm_config.json 路径")
    profile_show = profile_sub.add_parser("show", help="查看指定 profile")
    profile_show.add_argument("name")
    profile_show.add_argument("--config", type=Path, help="llm_config.json 路径")

    key_parser = subparsers.add_parser("key", help="管理 LLM API key")
    key_sub = key_parser.add_subparsers(dest="key_command", required=True)
    key_status_parser = key_sub.add_parser("status", help="查看 key 来源与掩码，不输出明文")
    key_status_parser.add_argument("--profile", help="按书 profile 查找 key_file")
    key_status_parser.add_argument("--config", type=Path, help="llm_config.json 路径")
    key_set_parser = key_sub.add_parser("set", help="从 stdin 或文件写入 API key")
    key_set_parser.add_argument("--profile", help="按书 profile 选择 key_file")
    key_set_parser.add_argument("--config", type=Path, help="llm_config.json 路径")
    key_set_parser.add_argument("--file", type=Path, help="从指定文件读取 key（文件本身不会被修改）")
    key_clear_parser = key_sub.add_parser("clear", help="删除当前 key 文件")
    key_clear_parser.add_argument("--profile", help="按书 profile 选择 key_file")
    key_clear_parser.add_argument("--config", type=Path, help="llm_config.json 路径")
    key_test_parser = key_sub.add_parser("test", help="用当前 key 发送一条最小请求")
    key_test_parser.add_argument("--profile", help="按书 profile 测试")
    key_test_parser.add_argument("--config", type=Path, help="llm_config.json 路径")
    return parser


def _read_glossary(path: Path | None) -> list[str]:
    if path is None:
        return []
    terms: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms.append(line)
    return list(dict.fromkeys(terms))


def _profile(args: argparse.Namespace) -> int:
    try:
        profiles = describe_profiles(args.config)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}")
        return 2

    config_path = args.config or DEFAULT_CONFIG_FILE
    if args.profile_command == "show":
        match = next((item for item in profiles if item["name"] == args.name), None)
        if match is None:
            print(f"ERROR: 未知 profile: {args.name}")
            return 2
        print(f"config: {config_path}")
        for key, value in match.items():
            print(f"{key}: {value}")
        return 0

    print(f"config: {config_path}")
    print(
        f"key: {'configured' if profiles[0]['keyConfigured'] else 'missing'} "
        f"({profiles[0]['keyFile']})"
    )
    for item in profiles:
        print(
            f"[{item['name']}] model={item['model']} "
            f"max_chars={item['maxChars']} max_tokens={item['maxTokens']} "
            f"thinking={item['thinking']} min_confidence={item['minConfidence']}"
        )
        glossary = item["glossary"] or "-"
        print(f"  glossary: {glossary} ({item['glossaryTerms']} terms)")
        if item["style"]:
            print(f"  style: {item['style']}")
    return 0


def _key(args: argparse.Namespace) -> int:
    command = args.key_command

    if command == "status":
        status = key_status(args.profile, args.config)
        print(f"key: {'configured' if status.configured else 'missing'}")
        print(f"source: {source_label(status)}")
        print(f"path: {status.path}")
        if status.masked:
            print(f"masked: {status.masked}")
        if status.env_override:
            print(f"note: {KEY_ENV} 已设置，读取时优先使用该变量指向的文件")
        return 0

    if command == "set":
        try:
            if args.file:
                value = args.file.read_text(encoding="utf-8")
            elif sys.stdin.isatty():
                value = getpass.getpass("API key: ")
            else:
                value = sys.stdin.readline()
            path = save_key(value, profile=args.profile, config_file=args.config)
        except (OSError, ValueError) as error:
            print(f"ERROR: {error}")
            return 2
        status = key_status(args.profile, args.config)
        print(f"saved: {path}")
        print(f"source: {source_label(status)}; masked: {status.masked}")
        if status.env_override:
            print(f"WARNING: {KEY_ENV} 已设置，运行时优先使用该变量指向的文件")
        return 0

    if command == "clear":
        try:
            path, removed = clear_key(args.profile, args.config)
        except OSError as error:
            print(f"ERROR: {error}")
            return 2
        print(("removed: " if removed else "missing: ") + str(path))
        return 0

    if command == "test":
        try:
            content = test_connection(args.profile, args.config)
        except Exception as error:
            print(f"ERROR: {error}")
            return 1
        print(f"OK: {content}")
        return 0

    return 2


def _review(args: argparse.Namespace) -> int:
    try:
        job = validate_job(args.job)
        profile = args.profile or str(job.get("titleBase", "")).strip() or None
        settings = load_settings(
            key_file=args.key_file,
            base_url=args.base_url,
            model=args.model,
            timeout=args.timeout,
            max_chars=args.max_chars,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            thinking=args.thinking,
            glossary=args.glossary,
            profile=profile,
            strict_profile=args.profile is not None,
        )
        glossary = _read_glossary(settings.glossary_file)
    except (OSError, ValueError, ValidationError) as error:
        print(f"ERROR: {error}")
        return 2

    if args.estimate:
        estimate = estimate_review(
            job,
            settings,
            max_chunks=max(args.limit, 0),
            sample_chunks=max(args.sample, 0),
            mode=args.mode,
        )
        profile_label = settings.profile_name or "-"
        print(
            f"ESTIMATE (no API call) [{args.mode} profile={profile_label} "
            f"model={settings.model}]"
        )
        sample_text = f", sample {estimate['sample']}" if estimate["sample"] else ""
        print(
            f"chunks: planned {estimate['plannedChunks']}, "
            f"selected {estimate['selectedChunks']}{sample_text}"
        )
        print(
            f"chars: planned {estimate['plannedChars']}, "
            f"selected {estimate['selectedChars']}"
        )
        tokens = estimate["estimated"]
        print(
            f"tokens ~ prompt {tokens['promptTokens']}, "
            f"completion {tokens['completionTokens']}, total {tokens['totalTokens']}"
        )
        cost = estimate["cost"]
        if cost:
            if cost["low"] is not None:
                print(
                    f"cost ~ {cost['currency']} {cost['low']:.2f}"
                    f"–{cost['high']:.2f} (off-peak–peak)"
                )
            else:
                print(f"cost ~ {cost['currency']} {cost['high']:.2f}")
        else:
            print("cost: 未配置 pricing，只估算 tokens")
        return 0

    report = review_job(
        job,
        settings,
        job_path=args.job,
        max_chunks=max(args.limit, 0),
        sample_chunks=max(args.sample, 0),
        mode=args.mode,
        glossary=glossary,
    )
    default_name = "llm_patch.json" if args.mode == "patch" else "llm_report.json"
    out_path = args.out or (args.job.parent / default_name)
    try:
        written = write_report(report, out_path)
    except OSError as error:
        print(f"ERROR: {error}")
        return 2

    summary = report["summary"]
    if summary.get("skipped"):
        print(f"SKIPPED: {summary.get('reason')}")
        print(f"key file: {settings.key_file}")
        print(f"report: {written}")
        return 0

    profile_label = settings.profile_name or "-"
    print(
        f"LLM {args.mode} [profile={profile_label} model={settings.model}]: "
        f"{summary['chunks']}/{summary['plannedChunks']} chunks, "
        f"{summary['issues']} issues, {summary['errors']} errors, "
        f"{summary['blocked']} blocked"
    )
    if summary.get("sample"):
        print(
            f"sample: {summary['sample']} chunks, "
            f"selected {summary['selectedChunks']}/{summary['plannedChunks']}"
        )
    usage = report["usage"]
    print(
        f"tokens: prompt={usage['promptTokens']}, completion={usage['completionTokens']}, "
        f"reasoning={usage['reasoningTokens']}, total={usage['totalTokens']}"
    )
    print(f"report: {written}")
    if args.strict and (
        summary["issues"] or summary["errors"] or summary["blocked"]
    ):
        return 3
    return 0


def _apply_patch(args: argparse.Namespace) -> int:
    try:
        job = json.loads(args.job.read_text(encoding="utf-8"))
        validate_job_data(job)
        patch_report = json.loads(args.patch.read_text(encoding="utf-8"))
        if not isinstance(patch_report, dict):
            raise ValueError("patch 文件根节点必须是对象")
        if patch_report.get("version") != 1 or patch_report.get("mode") != "patch":
            raise ValueError("patch 文件不是 review --mode patch 的输出")
        issues = patch_report.get("issues")
        if not isinstance(issues, list):
            raise ValueError("patch 文件缺少 issues 数组")
        policy = patch_report.get("policy") if isinstance(patch_report.get("policy"), dict) else {}
        min_confidence = (
            args.min_confidence
            or str(policy.get("minConfidence", "high"))
        )
        max_delta = policy.get("maxDelta") if isinstance(policy.get("maxDelta"), dict) else None
        result = apply_patches(
            job,
            issues,
            min_confidence=min_confidence,
            max_delta=max_delta,
        )
        validate_job_data(result.job)
    except (OSError, ValueError, ValidationError) as error:
        print(f"ERROR: {error}")
        return 2

    out_dir = args.out or (args.job.parent / "reviewed")
    diff_text = build_unified_diff(job, result.job)
    summary = {
        "applied": result.applied_count,
        "rejected": result.rejected_count,
        "segmentsChanged": result.segments_changed,
        "diffLines": len(diff_text.splitlines()),
    }
    if args.dry_run:
        print(
            f"DRY RUN: apply {summary['applied']}, reject {summary['rejected']}, "
            f"segments {summary['segmentsChanged']}, diff {summary['diffLines']} lines"
        )
        for item in result.rejected:
            print(f"REJECT segment={item['segment']} chunk={item['chunk']}: {item['reason']}")
        return 3 if args.strict and result.rejected_count else 0

    apply_report = {
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "job": str(args.job),
            "patch": str(args.patch),
            "minConfidence": min_confidence,
            "maxDelta": max_delta or {},
            "diff": "diff.patch",
        },
        "summary": summary,
        "applied": result.applied,
        "rejected": result.rejected,
    }

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        job_path = out_dir / "job.json"
        job_path.write_text(
            json.dumps(result.job, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        reviewed_text = "\n\n".join(
            str(segment.get("text", ""))
            for segment in result.job.get("segments", [])
        )
        (out_dir / "03_reviewed.txt").write_text(reviewed_text, encoding="utf-8")
        (out_dir / "diff.patch").write_text(diff_text, encoding="utf-8")
        apply_path = write_report(apply_report, out_dir / "patch_apply.json")
    except OSError as error:
        print(f"ERROR: {error}")
        return 2

    print(
        f"APPLIED: {summary['applied']} patches, rejected {summary['rejected']}, "
        f"segments changed {summary['segmentsChanged']}"
    )
    print(f"job: {out_dir / 'job.json'}")
    print(f"text: {out_dir / '03_reviewed.txt'}")
    print(f"diff: {out_dir / 'diff.patch'}")
    print(f"report: {apply_path}")
    if result.rejected_count:
        print("WARNING: 有补丁被拒绝，请查看 patch_apply.json")
    if args.strict and result.rejected_count:
        return 3
    return 0


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "prepare":
        out_dir = args.out or Path("work") / args.input.stem
        try:
            outcome = prepare_input(
                args.input,
                out_dir,
                title=args.title,
                page_limit=args.page_limit,
                max_segment_chars=args.max_segment_chars,
                calibre=args.calibre,
            )
        except (EbookError, OSError, ValueError, ValidationError) as error:
            print(f"ERROR: {error}")
            return 2

        if outcome.imported is not None and outcome.imported_text_path is not None:
            print(
                f"IMPORT: {outcome.imported.format} -> {outcome.imported_text_path} "
                f"({len(outcome.imported.text)} chars, "
                f"{len(outcome.imported.warnings)} warnings)"
            )
            for warning in outcome.imported.warnings:
                print(f"[import] {warning}")
        result = outcome.result
        summary = result.report["summary"]
        warnings = result.report["warnings"]
        print(
            f"OK: {summary['chapters']} chapters, {summary['segments']} segments, "
            f"max estimated pages {summary['max_estimated_pages']}"
        )
        print(f"job: {result.job_path}")
        print(f"report: {result.report_path}")
        print(f"warnings: {len(warnings)}")

        if args.verify:
            for warning in warnings:
                print(f"[{warning['level']}] {warning['code']}: {warning['message']}")

        if args.strict and warnings:
            return 3
        return 0

    if args.command == "validate":
        try:
            job = validate_job(args.job)
        except (OSError, ValidationError) as error:
            print(f"INVALID: {error}")
            return 1
        print(f"OK: {args.job} ({len(job['segments'])} segments)")
        return 0

    if args.command == "review":
        return _review(args)

    if args.command == "apply-patch":
        return _apply_patch(args)

    if args.command == "profile":
        return _profile(args)

    if args.command == "key":
        return _key(args)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
