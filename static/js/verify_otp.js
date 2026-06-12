(function() {
    document.addEventListener("DOMContentLoaded", function() {
        const otpInput = document.getElementById("otp");
        if(otpInput) {
            otpInput.focus();
            otpInput.addEventListener("input", function(e) {
                // Ensure only digits are entered
                this.value = this.value.replace(/[^0-9]/g, '');
            });
        }
        
        let timeLeft = 60;
        const timerSpan = document.getElementById('resendTimer');
        const resendLink = document.getElementById('resendLink');
        
        if (timerSpan && resendLink) {
            const countdown = setInterval(() => {
                timeLeft--;
                if (timeLeft <= 0) {
                    clearInterval(countdown);
                    timerSpan.classList.add('hidden');
                    resendLink.classList.remove('hidden');
                } else {
                    timerSpan.textContent = `Resend OTP (${timeLeft}s)`;
                }
            }, 1000);
        }
    });
})();
