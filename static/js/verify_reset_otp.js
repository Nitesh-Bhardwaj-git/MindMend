(function() {
    document.addEventListener("DOMContentLoaded", function() {
        const otpInput = document.getElementById("otp");
        if(otpInput) {
            otpInput.focus();
            otpInput.addEventListener("input", function(e) {
                this.value = this.value.replace(/[^0-9]/g, '');
            });
        }
    });
})();
