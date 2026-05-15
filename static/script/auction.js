/* =============================================
   BidVault — Auction Detail Page Script
   ============================================= */

/* ── Countdown Timer ── */
function parseEndTime(str) {
  if (!str) return NaN;
  var s = str.trim().replace(' ', 'T');
  var m = s.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/);
  if (m) {
    return new Date(
      parseInt(m[1]),
      parseInt(m[2]) - 1,
      parseInt(m[3]),
      parseInt(m[4]),
      parseInt(m[5]),
      parseInt(m[6] || '0')
    ).getTime();
  }
  return NaN;
}

function initTimer(endTimeStr) {
  var timerEl = document.getElementById('timerValue');
  if (!timerEl) return;

  var endTime = parseEndTime(endTimeStr);

  if (isNaN(endTime)) {
    timerEl.textContent = 'Invalid date';
    console.error('BidVault timer: could not parse end_time →', endTimeStr);
    return;
  }

  function tick() {
    var now  = Date.now();
    var diff = endTime - now;

    if (diff <= 0) {
      timerEl.textContent = 'Auction Ended';
      timerEl.className   = 'timer-value';
      clearInterval(interval);
      var bidForm = document.getElementById('bidForm');
      if (bidForm) {
        bidForm.querySelector('.btn-place-bid').disabled = true;
        bidForm.querySelector('.btn-place-bid').textContent = 'Auction Ended';
      }
      return;
    }

    var days    = Math.floor(diff / 86400000);
    var hours   = Math.floor((diff % 86400000) / 3600000);
    var minutes = Math.floor((diff % 3600000)  / 60000);
    var seconds = Math.floor((diff % 60000)    / 1000);

    var parts = [];
    if (days)    parts.push(days    + 'd');
    if (hours)   parts.push(hours   + 'h');
    if (minutes) parts.push(minutes + 'm');
    parts.push(seconds + 's');

    timerEl.textContent = parts.join(' ');

    if (diff < 3600000) {
      timerEl.className = 'timer-value ending-soon';
    }
  }

  tick();
  var interval = setInterval(tick, 1000);
}

/* ── Currency Converter ── */
var convRates   = null;
var convVisible = true;

var FALLBACK_RATES = {
  INR: 1, USD: 0.012, EUR: 0.011, GBP: 0.0095,
  JPY: 1.83, AED: 0.044, SGD: 0.016, CAD: 0.016, AUD: 0.019
};

var CURRENCY_SYMBOLS = {
  INR: '₹', USD: '$', EUR: '€', GBP: '£',
  JPY: '¥', AED: 'د.إ', SGD: 'S$', CAD: 'C$', AUD: 'A$'
};

var SHOW_CURRENCIES = ['USD', 'EUR', 'GBP', 'AED', 'JPY', 'SGD'];

function getBaseAmount() {
  var el = document.getElementById('bidAmountInput');
  if (!el) return 0;
  var v = parseFloat(el.value);
  return isNaN(v) ? 0 : v;
}

function convertAmount(amountINR, toCurrency) {
  var rates = convRates || FALLBACK_RATES;
  var rate  = rates[toCurrency] || 1;
  return (amountINR * rate).toFixed(2);
}

function updateConverter() {
  var base = getBaseAmount();
  if (!convVisible) return;

  SHOW_CURRENCIES.forEach(function(cur) {
    var el = document.getElementById('conv-' + cur);
    if (!el) return;
    if (base <= 0) {
      el.textContent = CURRENCY_SYMBOLS[cur] + '—';
      el.className   = 'conv-amount';
    } else {
      var converted = convertAmount(base, cur);
      var num = parseFloat(converted);
      var formatted = num >= 1000
        ? CURRENCY_SYMBOLS[cur] + num.toLocaleString('en-IN', {maximumFractionDigits: 0})
        : CURRENCY_SYMBOLS[cur] + converted;
      el.textContent = formatted;
      el.className   = 'conv-amount';
    }
  });
}

function toggleConverter() {
  convVisible = !convVisible;
  var grid = document.getElementById('converterGrid');
  var btn  = document.getElementById('convToggleBtn');
  if (grid) grid.style.display = convVisible ? 'grid' : 'none';
  if (btn)  btn.textContent    = convVisible ? 'Hide' : 'Show';
  if (convVisible) updateConverter();
}

function buildConverterHTML() {
  var items = SHOW_CURRENCIES.map(function(cur) {
    return (
      '<div class="conv-item">' +
        '<div class="conv-currency">' + cur + '</div>' +
        '<div class="conv-amount loading" id="conv-' + cur + '">—</div>' +
      '</div>'
    );
  }).join('');

  return (
    '<div class="converter-wrap">' +
      '<div class="converter-head">' +
        '<span class="converter-title">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round"><path d="M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>' +
          'Currency Converter' +
        '</span>' +
        '<button class="converter-toggle" id="convToggleBtn" onclick="toggleConverter()">Hide</button>' +
      '</div>' +
      '<div class="converter-grid" id="converterGrid">' + items + '</div>' +
    '</div>'
  );
}

function initConverter() {
  var wrap = document.getElementById('converterMount');
  if (!wrap) return;
  wrap.innerHTML = buildConverterHTML();

  var input = document.getElementById('bidAmountInput');
  if (input) {
    input.addEventListener('input', updateConverter);
    updateConverter();
  }
}

/* ── Number to Indian Words ── */
var _a = ['','One','Two','Three','Four','Five','Six','Seven','Eight','Nine',
          'Ten','Eleven','Twelve','Thirteen','Fourteen','Fifteen','Sixteen',
          'Seventeen','Eighteen','Nineteen'];
var _b = ['','','Twenty','Thirty','Forty','Fifty','Sixty','Seventy','Eighty','Ninety'];

function inWords(n) {
  n = Math.floor(n);
  if (n === 0) return 'Zero';
  if (n < 0)   return 'Minus ' + inWords(-n);
  var str = '';
  if (n >= 10000000) { str += inWords(Math.floor(n / 10000000)) + ' Crore '; n %= 10000000; }
  if (n >= 100000)   { str += inWords(Math.floor(n / 100000))   + ' Lakh ';  n %= 100000; }
  if (n >= 1000)     { str += inWords(Math.floor(n / 1000))     + ' Thousand '; n %= 1000; }
  if (n >= 100)      { str += _a[Math.floor(n / 100)]           + ' Hundred '; n %= 100; }
  if (n > 19)        { str += _b[Math.floor(n / 10)] + ' ' + _a[n % 10]; }
  else               { str += _a[n]; }
  return str.trim();
}

function updateBidWords() {
  var el  = document.getElementById('currentBidDisplay');
  var out = document.getElementById('bidAmountWords');
  if (!el || !out) return;
  var val = parseFloat(el.textContent.replace(/,/g, ''));
  if (!isNaN(val) && val > 0) {
    out.textContent = inWords(val) + ' Rupees';
  } else {
    out.textContent = '';
  }
}

function initBidWords() {
  updateBidWords();
  // Watch for live bid updates (e.g. WebSocket / polling updating the span)
  var target = document.getElementById('currentBidDisplay');
  if (target && window.MutationObserver) {
    var obs = new MutationObserver(updateBidWords);
    obs.observe(target, { childList: true, subtree: true, characterData: true });
  }
}

/* ── Toast notifications ── */
function showToast(msg, type) {
  var toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.className   = 'toast ' + (type || 'success') + ' show';
  setTimeout(function() { toast.className = 'toast'; }, 3000);
}

/* ── Form validation before submit ── */
function validateBid(event) {
  var minBid = parseFloat(
    document.getElementById('minBidValue')
      ? document.getElementById('minBidValue').dataset.min
      : 0
  );
  var amount = parseFloat(document.getElementById('bidAmountInput').value);

  if (!amount || amount < minBid) {
    event.preventDefault();
    showToast('Bid must be at least ₹' + minBid.toLocaleString('en-IN'), 'error');
    return false;
  }
  return true;
}

/* ── Init on DOM ready ── */
document.addEventListener('DOMContentLoaded', function() {

  // Timer
  var timerEl = document.getElementById('timerValue');
  if (timerEl && timerEl.dataset.endtime) {
    initTimer(timerEl.dataset.endtime);
  }

  // Currency converter
  initConverter();

  // Bid form validation
  var bidForm = document.getElementById('bidForm');
  if (bidForm) {
    bidForm.addEventListener('submit', validateBid);
  }

  // Bid amount in words
  initBidWords();

});