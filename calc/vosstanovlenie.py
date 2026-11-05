#!/usr/bin/env python3
"""Учения по восстановлению стенда из резервной копии.

Пересобирает стенд на текущем коде, снимает эталонный расчёт, делает копию,
удаляет схему данных, проверяет, что авария замечена, восстанавливает
и сверяет расчёт с эталоном. Пишет logs/vosstanovlenie.log.

    .venv/bin/python calc/vosstanovlenie.py
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ANSIBLE = BASE / ".venv" / "bin" / "ansible-playbook"
COMPOSE = ["docker-compose", "-f", str(BASE / "deploy" / "docker-compose.yml"),
           "--env-file", str(BASE / "deploy" / ".env")]
OUT = BASE / "deploy" / "runtime" / "out"
PLAN = "plan_2026-11-01.csv"
LOGS = BASE / "logs"


def playbook(name: str, log: str, *extra: str) -> tuple[int, float, str]:
    t0 = time.perf_counter()
    r = subprocess.run([str(ANSIBLE), name, *extra], cwd=BASE / "ansible",
                       capture_output=True, text=True)
    dt = time.perf_counter() - t0
    (LOGS / log).write_text(r.stdout + r.stderr, encoding="utf-8")
    recap = next((l for l in r.stdout.splitlines() if l.startswith("localhost ")), "")
    return r.returncode, dt, " ".join(recap.split()[2:5])


def main() -> None:
    out = []
    rc, dt, recap = playbook("deploy.yml", "deploy_tobe.log", "-e", "rebuild=true")
    out.append(f"развёртывание на текущем коде: код {rc}, {dt:.1f} с, {recap}")
    rc, dt, recap = playbook("run.yml", "run_tobe.log")
    out.append(f"эталонный расчёт: код {rc}, {dt:.1f} с")
    shutil.copy(OUT / PLAN, LOGS / "plan_etalon.csv")
    for line in (LOGS / "run_tobe.log").read_text(encoding="utf-8").splitlines():
        if '"msg"' in line:
            out.append(f"  {line.strip()}")

    rc, dt, recap = playbook("backup.yml", "backup.log")
    размер = (BASE / "deploy" / "backups" / "vektor_opt.dump").stat().st_size
    out.append(f"резервная копия: код {rc}, {dt:.1f} с, {размер / 1024:.1f} КБ")

    r = subprocess.run(COMPOSE + ["exec", "-T", "db", "psql", "-U", "sppr", "-d",
                                  "vektor_opt", "-c", "DROP SCHEMA zakupki CASCADE"],
                       capture_output=True, text=True)
    out.append(f"авария: схема данных удалена, код {r.returncode}")
    r = subprocess.run(COMPOSE + ["--profile", "job", "run", "--rm", "sppr"],
                       capture_output=True, text=True)
    out.append(f"проверка состояния после аварии: код {r.returncode}")
    out += [f"  {l}" for l in r.stdout.splitlines() if l.startswith("[")]

    rc, dt, recap = playbook("restore.yml", "restore.log")
    out.append(f"восстановление из копии с проверкой: код {rc}, {dt:.1f} с, {recap}")

    rc, dt, recap = playbook("run.yml", "run_after_restore.log")
    одинаково = (OUT / PLAN).read_bytes() == (LOGS / "plan_etalon.csv").read_bytes()
    out.append(f"расчёт после восстановления: код {rc}, проект заказа "
               f"{'совпадает с эталоном побайтово' if одинаково else 'ОТЛИЧАЕТСЯ от эталона'}")
    текст = "\n".join(out)
    print(текст)
    (LOGS / "vosstanovlenie.log").write_text(текст + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
