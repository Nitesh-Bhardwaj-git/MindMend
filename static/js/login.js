(function() {
    const config = window.LOGIN_CONFIG || {};
    let isDoctorLogin = false;

    // Elements
    const loginTypeBadge = document.getElementById('loginTypeBadge');
    const loginTitle = document.getElementById('loginTitle');
    const loginDescription = document.getElementById('loginDescription');
    const userLoginBtn = document.getElementById('userLoginBtn');
    const doctorLoginBtn = document.getElementById('doctorLoginBtn');
    const submitBtn = document.getElementById('submitBtn');
    const signupText = document.getElementById('signupText');
    const loginForm = document.getElementById('loginForm');

    if (userLoginBtn && doctorLoginBtn) {
        userLoginBtn.addEventListener('click', () => toggleLogin(false));
        doctorLoginBtn.addEventListener('click', () => toggleLogin(true));
    }

    function toggleLogin(isDoctor){
        isDoctorLogin = isDoctor;
        if (!loginForm) return;

        if(isDoctorLogin){
            if (loginTypeBadge) loginTypeBadge.innerHTML = '🩺 Doctor Access';
            if (loginTitle) loginTitle.textContent = 'Doctor Login';
            if (loginDescription) loginDescription.textContent = 'Access your professional dashboard and patient sessions.';
            if (submitBtn) submitBtn.textContent = 'Login as Doctor →';
            if (signupText) signupText.style.display = 'none';
            loginForm.action = config.doctorLoginUrl || '';

            if (doctorLoginBtn) doctorLoginBtn.classList.add('bg-[#00d1b2]','text-black');
            if (userLoginBtn) userLoginBtn.classList.remove('bg-[#00d1b2]','text-black');
            if (doctorLoginBtn) doctorLoginBtn.classList.remove('text-gray-500');
            if (userLoginBtn) userLoginBtn.classList.add('text-gray-500');
        } else {
            if (loginTypeBadge) loginTypeBadge.innerHTML = '🛡️ Secure Login';
            if (loginTitle) loginTitle.textContent = 'Welcome Back';
            if (loginDescription) loginDescription.textContent = 'Enter your credentials to access your wellness journey.';
            if (submitBtn) submitBtn.textContent = 'Login to Account →';
            if (signupText) signupText.style.display = 'block';
            loginForm.action = config.userLoginUrl || '';

            if (userLoginBtn) userLoginBtn.classList.add('bg-[#00d1b2]','text-black');
            if (doctorLoginBtn) doctorLoginBtn.classList.remove('bg-[#00d1b2]','text-black');
            if (userLoginBtn) userLoginBtn.classList.remove('text-gray-500');
            if (doctorLoginBtn) doctorLoginBtn.classList.add('text-gray-500');
        }
    }

    // Password toggle
    window.togglePasswordVis = function(){
        const passwordInput = document.getElementById('id_password');
        const toggleButton = document.getElementById('togglePassword');
        if (!passwordInput || !toggleButton) return;
        const eyeOpen = toggleButton.querySelector('.eye-open');
        const eyeClosed = toggleButton.querySelector('.eye-closed');
        if (!eyeOpen || !eyeClosed) return;
        
        if(passwordInput.type === 'password'){
            passwordInput.type = 'text';
            eyeOpen.classList.add('hidden');
            eyeClosed.classList.remove('hidden');
        } else {
            passwordInput.type = 'password';
            eyeOpen.classList.remove('hidden');
            eyeClosed.classList.add('hidden');
        }
    };

    // Hide error
    window.hideError = function(){
        const errorBox = document.getElementById('errorBox');
        if (errorBox) errorBox.classList.add('hidden');
    };
})();
