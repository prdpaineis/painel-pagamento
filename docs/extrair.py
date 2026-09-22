#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Painel da esteira de pagamento — extracao via XML-RPC (Odoo MMP).

Acoes da esteira:
    824  Solicitar pagamento
    825  Verificar pagamento

Escopo: SOMENTE linhas PENDENTES (state = 'i').
Classificacao: campo "Cumprimento Tipo da Pendencia" (cumprimento_tipo_pendencia_id).

Gera index.html (auto-contido, os dados vao embutidos no arquivo) na propria
pasta docs/, que e a raiz servida pelo GitHub Pages.
Uso:  python extrair.py
"""
import os, json, sys, xmlrpc.client
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter

# --- credenciais --------------------------------------------------------------
# procura nesta ordem: variavel ODOO_ENV_FILE, .env ao lado do script, pasta ACESSO MMP.
# No CI (GitHub Actions) nao ha arquivo .env: as credenciais vem prontas dos
# Secrets do repositorio, direto em os.environ.
AQUI = Path(__file__).resolve().parent
CANDIDATOS = [
    Path(os.environ["ODOO_ENV_FILE"]) if os.environ.get("ODOO_ENV_FILE") else None,
    AQUI / "odoo-mmp.env",
    Path(r"D:/Gabriel/Área de Trabalho/ACESSO MMP/odoo-mmp_generico.env"),
]
ENV = next((c for c in CANDIDATOS if c and c.exists()), None)

ACOES = {824: "Solicitar pagamento", 825: "Verificar pagamento"}

# tipos de pendencia agrupados por leitura de negocio
PENDENTE_CLIENTE = {"Análise"}
RECUSA = {
    "Recusada",
    "Recusada-Erro em nossa solicitação",
    "Recusada-Erro de análise do cliente",
    "Erro em nossa solicitação",
    "Erro de análise do cliente",
    "Cancelada-Erro em nossa solicitação",
    "Cancelada-Erro de análise do cliente",
}
# de quem e a culpa da recusa
RESP_NOSSA = {"Recusada-Erro em nossa solicitação", "Erro em nossa solicitação",
              "Cancelada-Erro em nossa solicitação"}
RESP_CLIENTE = {"Recusada-Erro de análise do cliente", "Erro de análise do cliente",
                "Cancelada-Erro de análise do cliente", "Procedimento Cliente",
                "Pagamento reagendado pelo Banco"}

CAMPOS = ["dossie_id", "create_date", "date_deadline", "user_id",
          "cumprimento_tipo_pendencia_id", "cumprimento_pagamento_valor",
          "cumprimento_lote", "tem_pendencia_cliente", "tipo_pendencia_cliente_id"]


def conectar():
    if ENV is not None:
        for linha in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in linha and not linha.startswith("#"):
                k, _, v = linha.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    elif not all(k in os.environ for k in ("ODOO_URL", "ODOO_DB", "ODOO_LOGIN", "ODOO_PASSWORD")):
        sys.exit("ERRO: credenciais nao encontradas. Copie odoo-mmp.env.example para "
                 "odoo-mmp.env e preencha, ou aponte ODOO_ENV_FILE.")
    url = os.environ["ODOO_URL"].rstrip("/")
    db, login, pw = os.environ["ODOO_DB"], os.environ["ODOO_LOGIN"], os.environ["ODOO_PASSWORD"]
    uid = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(db, login, pw, {})
    if not uid:
        sys.exit("ERRO: login recusado pelo Odoo. Confira o .env.")
    modelo = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)

    def executar(model, metodo, *args, **kw):
        return modelo.execute_kw(db, uid, pw, model, metodo, list(args), kw)

    return uid, executar


def faixa_idade(dias):
    if dias <= 3:   return "0-3 dias"
    if dias <= 7:   return "4-7 dias"
    if dias <= 15:  return "8-15 dias"
    if dias <= 30:  return "16-30 dias"
    if dias <= 60:  return "31-60 dias"
    if dias <= 90:  return "61-90 dias"
    return "90+ dias"


FAIXAS = ["0-3 dias", "4-7 dias", "8-15 dias", "16-30 dias",
          "31-60 dias", "61-90 dias", "90+ dias"]


def main():
    print("Conectando no Odoo...")
    uid, x = conectar()
    print(f"  UID {uid}\n")

    hoje = datetime.now()
    registros = []

    for aid, nome in ACOES.items():
        print(f"Baixando pendentes de '{nome}' (acao {aid})...")
        linhas = x("project.task.action.line", "search_read",
                   [("action_id", "=", aid), ("state", "=", "i")],
                   fields=CAMPOS, limit=0)
        print(f"  {len(linhas)} linhas")
        for l in linhas:
            l["_acao"] = nome
            l["_acao_id"] = aid
        registros.extend(linhas)

    # grupo vem do dossie
    dossie_ids = sorted({r["dossie_id"][0] for r in registros if r.get("dossie_id")})
    print(f"\nLendo {len(dossie_ids)} dossies (grupo / fase / estado)...")
    dossies = {}
    for i in range(0, len(dossie_ids), 500):
        for d in x("dossie.dossie", "read", dossie_ids[i:i + 500],
                   fields=["grupo_id", "fase_id", "state", "name"]):
            dossies[d["id"]] = d
        print(f"  {min(i+500, len(dossie_ids))}/{len(dossie_ids)}", end="\r")
    print()

    itens = []
    for r in registros:
        did = r["dossie_id"][0] if r.get("dossie_id") else None
        dos = dossies.get(did, {})
        criado = r.get("create_date") or ""
        try:
            dt = datetime.strptime(criado, "%Y-%m-%d %H:%M:%S")
            dias = (hoje - dt).days
        except ValueError:
            dt, dias = None, 0
        tipo = r["cumprimento_tipo_pendencia_id"][1] if r.get("cumprimento_tipo_pendencia_id") else "(sem tipo)"
        itens.append({
            "id": r["id"],
            "acao": r["_acao"],
            "grupo": dos.get("grupo_id")[1] if dos.get("grupo_id") else "(sem grupo)",
            "fase": dos.get("fase_id")[1] if dos.get("fase_id") else "(sem fase)",
            "caso": r["dossie_id"][1] if r.get("dossie_id") else "",
            "tipo": tipo,
            "criado": criado[:10],
            "dias": dias,
            "faixa": faixa_idade(dias),
            "resp": r["user_id"][1] if r.get("user_id") else "(sem responsável)",
            "valor": r.get("cumprimento_pagamento_valor") or 0.0,
            "lote": r.get("cumprimento_lote") or "",
            "lote_rot": (r.get("cumprimento_lote") or "").strip() or "(sem lote)",
            "prazo": r.get("date_deadline") or "",
            "pend_cliente": {"s": "Sim", "n": "Não", "e": "Expirado"}.get(r.get("tem_pendencia_cliente"), ""),
            "tipo_pend_cliente": r["tipo_pendencia_cliente_id"][1] if r.get("tipo_pendencia_cliente_id") else "",
        })

    payload = {
        "gerado_em": hoje.strftime("%d/%m/%Y %H:%M"),
        "faixas": FAIXAS,
        "pendente_cliente": sorted(PENDENTE_CLIENTE),
        "recusa": sorted(RECUSA),
        "resp_nossa": sorted(RESP_NOSSA),
        "resp_cliente": sorted(RESP_CLIENTE),
        "itens": itens,
    }

    base = Path(__file__).resolve().parent
    (base / "dados.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    modelo_html = (base / "painel_template.html").read_text(encoding="utf-8")
    saida = modelo_html.replace("/*__DADOS__*/null",
                                json.dumps(payload, ensure_ascii=False))
    (base / "index.html").write_text(saida, encoding="utf-8")

    # versao para publicar como Artifact: so o miolo, sem <html>/<head>/<body>
    ini, fim = saida.find("<!--ARTEFATO-->"), saida.find("<!--/ARTEFATO-->")
    if ini == -1 or fim == -1:
        sys.exit("ERRO: marcadores <!--ARTEFATO--> nao encontrados no template.")
    (base / "artefato.html").write_text(
        saida[ini + len("<!--ARTEFATO-->"):fim].strip() + "\n", encoding="utf-8")

    print(f"\nOK — {len(itens)} pendencias.")
    print("  " + str(base / "dados.json"))
    print("  " + str(base / "index.html") + "   <- painel publico (docs/, GitHub Pages)")
    print("  " + str(base / "artefato.html") + " <- versao para publicar como Artifact")

    # resumo no console
    print("\nPor acao x tipo de pendencia:")
    c = Counter((i["acao"], i["tipo"]) for i in itens)
    for (a, t), n in sorted(c.items(), key=lambda kv: -kv[1]):
        print(f"  {a:22s} {t:40s} {n:6d}")
    print("\nPor grupo:")
    for g, n in Counter(i["grupo"] for i in itens).most_common(20):
        print(f"  {g[:40]:40s} {n:6d}")


if __name__ == "__main__":
    main()
