(function() {
  const config = window.PAYMENT_CONFIG || {};

  // Razorpay
  const payBtn = document.getElementById('rzp-pay-btn');
  const errorMsg = document.getElementById('rzp-error-msg');

  if (payBtn) {
    var rzpOptions = {
      key:         config.key,
      amount:      config.amount,
      currency:    "INR",
      name:        "MindMend",
      description: "Counsellor Session – " + (config.counsellorName || ""),
      order_id:    config.orderId,
      prefill: {
        name:  config.userName || "",
        email: config.userEmail || ""
      },
      theme: { color: "#00d1b2" },
      handler: function(response) {
        document.getElementById('rzp_order_id').value   = response.razorpay_order_id;
        document.getElementById('rzp_payment_id').value = response.razorpay_payment_id;
        document.getElementById('rzp_signature').value  = response.razorpay_signature;
        document.getElementById('razorpay-verify-form').submit();
      },
      modal: {
        ondismiss: function() {
          if (errorMsg) {
            errorMsg.textContent = 'Payment window closed. Click the button again to retry.';
            errorMsg.classList.remove('hidden');
          }
        }
      }
    };

    payBtn.addEventListener('click', function(e) {
      e.preventDefault();
      if (errorMsg) errorMsg.classList.add('hidden');
      var rzp = new Razorpay(rzpOptions);
      rzp.on('payment.failed', function(resp) {
        if (errorMsg) {
          errorMsg.textContent = 'Payment failed: ' + (resp.error.description || 'Please try again.');
          errorMsg.classList.remove('hidden');
        }
      });
      rzp.open();
    });
  }

  // Timer
  const createdAtSecs = parseFloat(config.bookingTimestamp || '0');
  if (createdAtSecs) {
    const creationTime = new Date(createdAtSecs * 1000).getTime();
    const expirationTime = creationTime + (15 * 60 * 1000); // 15 minutes limit
    const timerDisplay = document.getElementById('countdown-timer');

    function updateTimer() {
      const now = new Date().getTime();
      const distance = expirationTime - now;

      if (distance <= 0) {
        clearInterval(interval);
        if (timerDisplay) {
          timerDisplay.textContent = "00:00";
          timerDisplay.classList.add('text-red-500');
        }
        if (payBtn) {
          payBtn.disabled = true;
          payBtn.classList.add('opacity-50', 'cursor-not-allowed');
        }
        if (errorMsg) {
          errorMsg.innerHTML = 'This reservation has expired. Please <a href="' + (config.bookingRedirectUrl || '#') + '" class="underline text-red-300 hover:text-white">book a new session</a>.';
          errorMsg.classList.remove('hidden');
        }
        return;
      }

      const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((distance % (1000 * 60)) / 1000);
      
      const mStr = minutes < 10 ? "0" + minutes : minutes;
      const sStr = seconds < 10 ? "0" + seconds : seconds;
      
      if (timerDisplay) {
        timerDisplay.textContent = mStr + ":" + sStr;

        // Visual warning when under 2 minutes
        if (minutes < 2) {
           timerDisplay.classList.add('text-red-400');
        }
      }
    }

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
  }
})();
