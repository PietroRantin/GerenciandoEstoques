/* Estoque Fácil — comportamentos de interface (sem regras de negócio). */
(function () {
  "use strict";

  // Confirmação antes de ações destrutivas: <form data-confirmar="mensagem">
  document.addEventListener("submit", function (ev) {
    var form = ev.target;
    var msg = form.getAttribute("data-confirmar");
    if (msg && !window.confirm(msg)) { ev.preventDefault(); return; }
    // Evita duplo envio (ex.: entrada registrada duas vezes)
    if (!ev.defaultPrevented && !form.hasAttribute("data-sem-trava")) {
      setTimeout(function () {
        form.querySelectorAll("button[type=submit]").forEach(function (b) { b.disabled = true; });
      }, 0);
    }
  });

  // Máscara de dinheiro: formata ao sair do campo (ex.: 1234.5 -> 1.234,50)
  function formatarDinheiro(input) {
    var v = input.value.trim().replace(/R\$\s?/, "");
    if (!v) return;
    if (v.indexOf(",") >= 0) v = v.replace(/\./g, "").replace(",", ".");
    var n = parseFloat(v);
    if (isNaN(n)) return;
    input.value = n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  document.addEventListener("focusout", function (ev) {
    if (ev.target.matches && ev.target.matches("input.dinheiro")) formatarDinheiro(ev.target);
  });
  document.addEventListener("input", function (ev) {
    var el = ev.target;
    if (el.matches && (el.matches("input.dinheiro") || el.matches("input.quantidade"))) {
      var limpo = el.value.replace(/[^0-9.,]/g, "");
      if (limpo !== el.value) el.value = limpo;
    }
  });

  // Seletor de produto com busca (nome, código/SKU ou leitor de código de barras)
  window.ativarSeletorProduto = function (container) {
    var filtro = container.querySelector(".filtro-produto");
    var select = container.querySelector(".select-produto");
    if (!filtro || !select) return;
    var opcoes = Array.prototype.slice.call(select.options, 1).map(function (o) {
      return { el: o, texto: (o.text + " " + (o.dataset.codigos || "")).toLowerCase() };
    });
    function aplicar(selecionarExato) {
      var termo = filtro.value.trim().toLowerCase();
      var visiveis = [];
      opcoes.forEach(function (o) {
        var ok = !termo || o.texto.indexOf(termo) >= 0;
        o.el.hidden = !ok; o.el.disabled = !ok;
        if (ok) visiveis.push(o);
      });
      var exato = opcoes.filter(function (o) { return termo && (o.el.dataset.codigos || "").split(" ").indexOf(termo) >= 0; });
      var escolha = exato.length === 1 ? exato[0] : (visiveis.length === 1 ? visiveis[0] : null);
      if (escolha && (selecionarExato || visiveis.length === 1)) {
        select.value = escolha.el.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }
    filtro.addEventListener("input", function () { aplicar(false); });
    filtro.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") { ev.preventDefault(); aplicar(true); }  // leitores enviam Enter
    });
  };
  document.querySelectorAll(".seletor-produto").forEach(window.ativarSeletorProduto);

  // Formatação de números para exibição
  window.fmtQtd = function (n) { return Number(n).toLocaleString("pt-BR", { maximumFractionDigits: 3 }); };
  window.fmtBRL = function (n) { return Number(n).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }); };
})();
