/* Formulários de entrada/saída: mostra os campos de lote, validade e série
   conforme o produto escolhido. As validações reais ficam no servidor. */
(function () {
  "use strict";
  var form = document.getElementById("form-movimento");
  if (!form) return;
  var modo = form.dataset.modo;
  var select = form.querySelector(".select-produto");
  var info = document.getElementById("info-produto");
  var produtoAtual = null;

  function mostrar(seletor, visivel) {
    form.querySelectorAll(seletor).forEach(function (el) { el.hidden = !visivel; });
  }
  function esc(t) { var d = document.createElement("div"); d.textContent = t; return d.innerHTML; }

  function atualizarSeries(p) {
    var lista = document.getElementById("lista-series");
    var hidden = document.getElementById("numeros_serie");
    if (!lista) return;
    var marcados = (hidden.value || "").split(",").map(function (s) { return s.trim(); });
    lista.innerHTML = "";
    if (!p.series.length) { lista.innerHTML = '<span class="text-muted">Nenhuma unidade em estoque.</span>'; return; }
    p.series.forEach(function (s, i) {
      var id = "serie_" + i;
      var wrap = document.createElement("div");
      wrap.className = "form-check form-check-inline border rounded px-4 py-2";
      wrap.innerHTML = '<input class="form-check-input" type="checkbox" id="' + id + '" value="' + esc(s) + '"' +
        (marcados.indexOf(s) >= 0 ? " checked" : "") + '><label class="form-check-label" for="' + id + '">' + esc(s) + "</label>";
      lista.appendChild(wrap);
    });
    lista.addEventListener("change", function () {
      var sel = Array.prototype.map.call(lista.querySelectorAll("input:checked"), function (c) { return c.value; });
      hidden.value = sel.join(", ");
      document.getElementById("quantidade").value = sel.length || "";
    });
  }

  function atualizarLotes(p) {
    var lote = document.getElementById("lote_id");
    if (!lote) return;
    var escolhido = form.dataset.lote || lote.value;
    lote.length = 1;
    p.lotes.forEach(function (l) {
      var o = document.createElement("option");
      o.value = l.id;
      o.textContent = "Lote " + l.numero + (l.validade ? " · validade " + l.validade : "") +
        " · " + fmtQtd(l.quantidade) + " " + p.unidade + (l.vencido ? " (VENCIDO)" : "");
      if (String(l.id) === String(escolhido)) o.selected = true;
      lote.appendChild(o);
    });
  }

  function carregar() {
    var id = select.value;
    if (!id) { info.hidden = true; mostrar(".campo-lote, .campo-serie", false); produtoAtual = null; return; }
    fetch(form.dataset.api.replace(/0$/, id), { headers: { "Accept": "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (p) {
        produtoAtual = p;
        info.hidden = false;
        info.innerHTML = "<strong>" + esc(p.nome) + "</strong> · Estoque atual: <span class='qtd-grande'>" +
          fmtQtd(p.estoque_atual) + " " + esc(p.unidade) + "</span>" +
          (p.estoque_atual <= p.ponto_pedido ? " <span class='badge text-bg-warning'>precisa repor</span>" : "");
        var usaLote = p.controla_lote || p.controla_validade;
        mostrar(".campo-lote", usaLote);
        mostrar(".campo-serie", p.controla_serie);
        if (modo === "entrada") {
          mostrar(".campo-validade", p.controla_validade || p.controla_lote);
          mostrar(".obrig-lote", p.controla_lote);
          mostrar(".obrig-validade", p.controla_validade);
          var custo = document.getElementById("valor_unitario");
          if (custo && !custo.value && p.preco_custo) custo.value = p.preco_custo.toLocaleString("pt-BR", { minimumFractionDigits: 2 });
        } else {
          atualizarLotes(p);
          if (p.controla_serie) atualizarSeries(p);
        }
        verificarQuantidade();
      })
      .catch(function () { info.hidden = false; info.textContent = "Não foi possível carregar os dados do produto. Verifique a conexão."; });
  }

  function verificarQuantidade() {
    var aviso = document.getElementById("aviso-qtd");
    if (!aviso || !produtoAtual) return;
    var q = parseFloat((document.getElementById("quantidade").value || "0").replace(/\./g, "").replace(",", "."));
    if (q > produtoAtual.estoque_atual) {
      aviso.className = "form-text text-danger fw-bold";
      aviso.textContent = "Estoque insuficiente: disponível " + fmtQtd(produtoAtual.estoque_atual) + " " + produtoAtual.unidade + ".";
    } else { aviso.className = "form-text"; aviso.textContent = ""; }
  }

  select.addEventListener("change", carregar);
  var qtd = document.getElementById("quantidade");
  if (qtd) qtd.addEventListener("input", verificarQuantidade);
  if (select.value) carregar();
})();
