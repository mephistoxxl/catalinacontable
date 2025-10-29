// Empresa Selector Enhanced Functionality
document.addEventListener('DOMContentLoaded', function() {
    const empresaSelect = document.getElementById('empresa');
    
    if (!empresaSelect) return;

    // Add loading state when fetching companies
    const originalCargarEmpresas = window.cargarEmpresas;
    
    // Enhance the select with animations
    empresaSelect.addEventListener('focus', function() {
        this.style.transform = 'scale(1.01)';
    });

    empresaSelect.addEventListener('blur', function() {
        this.style.transform = 'scale(1)';
    });

    // Add change animation
    empresaSelect.addEventListener('change', function() {
        // Add success state briefly
        this.classList.add('success');
        
        // Create a ripple effect
        const ripple = document.createElement('span');
        ripple.style.position = 'absolute';
        ripple.style.borderRadius = '50%';
        ripple.style.backgroundColor = 'rgba(16, 185, 129, 0.4)';
        ripple.style.width = '20px';
        ripple.style.height = '20px';
        ripple.style.animation = 'ripple 0.6s ease-out';
        ripple.style.pointerEvents = 'none';
        
        const rect = this.getBoundingClientRect();
        ripple.style.left = (rect.width / 2) + 'px';
        ripple.style.top = (rect.height / 2) + 'px';
        ripple.style.transform = 'translate(-50%, -50%)';
        
        this.parentElement.style.position = 'relative';
        this.parentElement.appendChild(ripple);
        
        setTimeout(() => {
            ripple.remove();
            this.classList.remove('success');
        }, 600);
        
        // Save last selected empresa to localStorage
        if (this.value) {
            localStorage.setItem('lastSelectedEmpresa', this.value);
            localStorage.setItem('lastSelectedEmpresaText', this.options[this.selectedIndex].text);
        }
    });

    // Observer to watch for dynamic changes
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                // Options were added/changed
                console.log('Empresas selector updated');
            }
        });
    });

    observer.observe(empresaSelect, { childList: true });

    // Restore last selected empresa if available
    const lastSelectedEmpresa = localStorage.getItem('lastSelectedEmpresa');
    if (lastSelectedEmpresa) {
        setTimeout(() => {
            const option = empresaSelect.querySelector(`option[value="${lastSelectedEmpresa}"]`);
            if (option) {
                empresaSelect.value = lastSelectedEmpresa;
                // Add a subtle highlight to show it was auto-selected
                empresaSelect.style.borderColor = '#10b981';
                setTimeout(() => {
                    empresaSelect.style.borderColor = '';
                }, 2000);
            }
        }, 500);
    }

    // Add tooltip showing the last selected company
    const lastSelectedText = localStorage.getItem('lastSelectedEmpresaText');
    if (lastSelectedText) {
        const tooltip = document.createElement('div');
        tooltip.className = 'text-xs text-gray-500 mt-1 italic';
        tooltip.innerHTML = `<i class="fas fa-info-circle mr-1"></i>Última empresa: ${lastSelectedText}`;
        tooltip.style.opacity = '0';
        tooltip.style.transition = 'opacity 0.3s ease';
        
        const empresaWrapper = empresaSelect.parentElement;
        empresaWrapper.appendChild(tooltip);
        
        setTimeout(() => {
            tooltip.style.opacity = '1';
        }, 300);
    }

    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Alt + E to focus empresa selector
        if (e.altKey && e.key === 'e') {
            e.preventDefault();
            empresaSelect.focus();
        }
    });

    // Add smooth scroll to empresa field if there's an error
    const empresaError = document.getElementById('empresa-error');
    if (empresaError && !empresaError.classList.contains('hidden')) {
        empresaSelect.scrollIntoView({ behavior: 'smooth', block: 'center' });
        empresaSelect.focus();
    }
});

// Add ripple animation CSS
const style = document.createElement('style');
style.textContent = `
    @keyframes ripple {
        0% {
            width: 20px;
            height: 20px;
            opacity: 0.5;
        }
        100% {
            width: 200px;
            height: 200px;
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
