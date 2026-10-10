(function () {
  var modal = document.getElementById('layby-modal');
  var activeForm = null;
  var moneyPrefix = 'MWK ';

  function fmt(value) {
    return moneyPrefix + Number(value || 0).toLocaleString(undefined, {
      maximumFractionDigits: 0,
    });
  }

  function updateLine(select) {
    var form = select.form;
    var max = parseInt(form.dataset.max, 10);
    var qty = parseInt(form.querySelector('input[name="quantity"]').value, 10);
    var display = document.getElementById('qty_display_' + form.dataset.context);
    var total = document.getElementById('line_total_' + form.dataset.context);
    qty = Math.max(1, Math.min(qty, max || 1));
    form.querySelector('input[name="quantity"]').value = qty;
    display.textContent = qty;
    total.textContent = fmt(qty * parseFloat(form.dataset.price));
  }

  function setPayment(btn) {
    var form = btn.closest('.sale-form');
    var payment = btn.dataset.payment;
    form.querySelector('input[name="payment"]').value = payment;
    form.querySelectorAll('.pay-option').forEach(function (opt) {
      opt.classList.toggle('active', opt === btn);
    });
  }

  function openModal(form) {
    activeForm = form;
    var field = document.getElementById('layby-name');
    var error = document.getElementById('layby-name-error');
    error.hidden = true;
    modal.hidden = false;
    window.setTimeout(function () { field.focus(); }, 60);
  }

  document.addEventListener('click', function (event) {
    var btn = event.target.closest('.pay-option');
    if (btn) { setPayment(btn); return; }

    var qtyBtn = event.target.closest('[data-qty]');
    if (qtyBtn) {
      var form = qtyBtn.closest('.sale-form');
      if (!form) { return; }
      var input = form.querySelector('input[name="quantity"]');
      var max = parseInt(form.dataset.max, 10);
      var qty = parseInt(input.value, 10);
      qty += (qtyBtn.dataset.qty === 'plus') ? 1 : -1;
      if (max > 0) { qty = Math.max(1, Math.min(qty, max)); } else { qty = Math.max(qty, 1); }
      input.value = qty;
      updateLine(input);
      return;
    }

    var del = event.target.closest('[data-role="delete"]');
    if (del) {
      var message = del.dataset.message || 'Delete this?';
      if (window.confirm(message)) { del.closest('form').submit(); }
      return;
    }
  });

  document.addEventListener('submit', function (event) {
    var form = event.target.closest ? event.target.closest('.sale-form') : null;
    if (!form) { return; }
    var payment = form.querySelector('input[name="payment"]').value;
    if (payment === 'layby') {
      event.preventDefault();
      openModal(form);
    }
  });

  document.getElementById('layby-submit').addEventListener('click', function () {
    if (!activeForm) { modal.hidden = true; return; }
    var name = document.getElementById('layby-name').value.trim();
    var error = document.getElementById('layby-name-error');
    if (!name) {
      error.hidden = false;
      document.getElementById('layby-name').focus();
      return;
    }
    activeForm.querySelector('input[name="customer_name"]').value = name;
    activeForm.querySelector('input[name="customer_phone"]').value = document.getElementById('layby-phone').value.trim();
    modal.hidden = true;
    activeForm.submit();
  });

  var dayPicker = document.querySelector('[data-onchange-target]');
  if (dayPicker) {
    dayPicker.addEventListener('change', function () {
      window.location = '/sell/?date=' + dayPicker.value;
    });
  }
})();