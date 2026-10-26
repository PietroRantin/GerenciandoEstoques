/* Tela de venda: adiciona/remove linhas e mostra o total. A baixa de
   estoque e a validação final acontecem no servidor (sales_service). */
(function () {
  "use strict";
  var tbody = document.querySelector("#tabela-itens tbody");
  var modelo = tbody.querySelector(".linha-item").cloneNode(true);
  function num(v) {
    v = (v || "").trim(); if (!v) return NaN;
    if (v.indexOf(",") >= 0) v = v.replace(/\./g, "").replace(",", ".");
    return parseFloat(v);
  }
  function recalcular() {
    var total = 0;
    tbody.querySelectorAll(".linha-item").forEach(function (tr) {
      var sel = tr.querySelector(".item-produto");
      var opt = sel.options[sel.selectedIndex];
      var qtd = num(tr.querySelector(".item-qtd").value) || 0;
      var preco = num(tr.querySelector(".item-preco").value);
      if (isNaN(preco)) preco = opt && opt.dataset.preco ? parseFloat(opt.dataset.preco) : 0;
      var sub = qtd * preco;
      total += sub;
      tr.querySelector(".item-subtotal").textContent = fmtBRL(sub);
      var aviso = tr.querySelector(".aviso-estoque");
      var estoque = opt && opt.dataset.estoque ? parseFloat(opt.dataset.estoque) : null;
      aviso.textContent = (estoque !== null && qtd > estoque) ? "Estoque insuficiente (disponível: " + fmtQtd(estoque) + ")" : "";
    });
    document.getElementById("total-venda").textContent = fmtBRL(total);
  }
  function novaLinha(productId) {
    var tr = modelo.cloneNode(true);
    tr.querySelector(".item-produto").value = productId || "";
    tr.querySelector(".item-qtd").value = "1";
    tr.querySelector(".item-preco").value = "";
    tbody.appendChild(tr);
    recalcular();
    return tr;
  }
  document.getElementById("adicionar").addEventListener("click", function () { novaLinha().querySelector("select").focus(); });
  tbody.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".remover");
    if (!btn) return;
    if (tbody.querySelectorAll(".linha-item").length > 1) btn.closest("tr").remove();
    else { var tr = btn.closest("tr"); tr.querySelector("select").value = ""; tr.querySelector(".item-qtd").value = "1"; }
    recalcular();
  });
  tbody.addEventListener("input", recalcular);
  tbody.addEventListener("change", recalcular);

  // Busca rápida / leitor de código de barras: Enter adiciona o produto
  var busca = document.getElementById("busca-venda");
  busca.addEventListener("keydown", function (ev) {
    if (ev.key !== "Enter") return;
    ev.preventDefault();
    var termo = busca.value.trim().toLowerCase();
    if (!termo) return;
    var opcoes = Array.prototype.slice.call(modelo.querySelector(".item-produto").options, 1);
    var achado = opcoes.filter(function (o) { return (o.dataset.codigos || "").split(" ").indexOf(termo) >= 0; })[0] ||
                 opcoes.filter(function (o) { return o.text.toLowerCase().indexOf(termo) >= 0; })[0];
    if (!achado) { busca.classList.add("is-invalid"); return; }
    busca.classList.remove("is-invalid");
    // Se o produto já está na venda, soma 1 na quantidade
    var existente = Array.prototype.filter.call(tbody.querySelectorAll(".item-produto"), function (s) { return s.value === achado.value; })[0];
    if (existente) {
      var q = existente.closest("tr").querySelector(".item-qtd");
      q.value = String((num(q.value) || 0) + 1);
    } else {
      var vazia = Array.prototype.filter.call(tbody.querySelectorAll(".item-produto"), function (s) { return !s.value; })[0];
      if (vazia) vazia.value = achado.value; else novaLinha(achado.value);
    }
    busca.value = "";
    recalcular();
  });
  recalcular();
})();
