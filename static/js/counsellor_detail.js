function switchTab(tabId, buttonElement) {
    // Hide all tab panels
    document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    
    // Show selected panel
    const targetPanel = document.getElementById('tab-' + tabId);
    if (targetPanel) {
        targetPanel.classList.add('active');
    }

    // Reset all tab button styles
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.className = "tab-btn flex-1 py-3 px-4 rounded-xl text-sm font-bold tracking-wide transition-all duration-300 text-gray-400 hover:text-white hover:bg-white/5 whitespace-nowrap";
    });

    // Set active style on current button
    buttonElement.className = "tab-btn flex-1 py-3 px-4 rounded-xl text-sm font-bold tracking-wide transition-all duration-300 whitespace-nowrap bg-[#00d1b2] text-black shadow-md";
}
