// sidebar.js - Script dedicado para el manejo de dropdowns del sidebar
(function() {
    'use strict';
    
    console.log('🚀 Iniciando sidebar.js...');
    
    // Variables globales
    let dropdownButtons = [];
    let isInitialized = false;
    
    // Función para inicializar el sidebar
    function initializeSidebar() {
        console.log('📋 Inicializando sidebar...');
        
        // Buscar todos los botones dropdown
        dropdownButtons = document.querySelectorAll('.dropdown-toggle');
        console.log('🔍 Botones encontrados:', dropdownButtons.length);
        
        if (dropdownButtons.length === 0) {
            console.warn('⚠️ No se encontraron botones dropdown');
            return false;
        }
        
        // Configurar cada botón
        dropdownButtons.forEach(function(button, index) {
            console.log(`🔧 Configurando botón ${index + 1}:`, button);
            
            // Remover listeners previos si existen
            const newButton = button.cloneNode(true);
            button.parentNode.replaceChild(newButton, button);
            
            // Agregar nuevo listener
            newButton.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                console.log('🖱️ Click detectado en botón:', this);
                
                handleDropdownClick(this);
            });
        });
        
        // Actualizar la referencia a los botones
        dropdownButtons = document.querySelectorAll('.dropdown-toggle');
        
        // Agregar listener para cerrar dropdowns al hacer click fuera
        document.addEventListener('click', function(e) {
            if (!e.target.closest('.dropdown-toggle') && !e.target.closest('[id^="dropdown-"]')) {
                closeAllDropdowns();
            }
        });
        
        isInitialized = true;
        console.log('✅ Sidebar inicializado correctamente');
        return true;
    }
    
    // Función para manejar el click en un dropdown
    function handleDropdownClick(button) {
        console.log('🎯 Manejando click en dropdown...');
        
        // Obtener el ID del dropdown
        const targetId = button.getAttribute('aria-controls');
        console.log('🏷️ Target ID:', targetId);
        
        if (!targetId) {
            console.error('❌ No se encontró aria-controls en el botón');
            return;
        }
        
        // Buscar el dropdown
        const dropdown = document.getElementById(targetId);
        console.log('📦 Dropdown encontrado:', dropdown);
        
        if (!dropdown) {
            console.error('❌ No se encontró el dropdown con ID:', targetId);
            return;
        }
        
        // Obtener la flecha
        const arrow = button.querySelector('.arrow');
        console.log('➡️ Flecha encontrada:', arrow);
        
        // Cerrar otros dropdowns
        closeOtherDropdowns(button);
        
        // Toggle el dropdown actual
        const isHidden = dropdown.classList.contains('hidden');
        console.log('👁️ Dropdown está oculto:', isHidden);
        
        if (isHidden) {
            // Mostrar dropdown
            dropdown.classList.remove('hidden');
            if (arrow) {
                arrow.style.transform = 'rotate(90deg)';
            }
            console.log('📖 Dropdown mostrado');
        } else {
            // Ocultar dropdown
            dropdown.classList.add('hidden');
            if (arrow) {
                arrow.style.transform = 'rotate(0deg)';
            }
            console.log('📕 Dropdown ocultado');
        }
    }
    
    // Función para cerrar otros dropdowns
    function closeOtherDropdowns(currentButton) {
        console.log('🔄 Cerrando otros dropdowns...');
        
        dropdownButtons.forEach(function(button) {
            if (button !== currentButton) {
                const targetId = button.getAttribute('aria-controls');
                if (targetId) {
                    const dropdown = document.getElementById(targetId);
                    const arrow = button.querySelector('.arrow');
                    
                    if (dropdown && !dropdown.classList.contains('hidden')) {
                        dropdown.classList.add('hidden');
                        if (arrow) {
                            arrow.style.transform = 'rotate(0deg)';
                        }
                        console.log('📕 Cerrado dropdown:', targetId);
                    }
                }
            }
        });
    }
    
    // Función para cerrar todos los dropdowns
    function closeAllDropdowns() {
        console.log('🔒 Cerrando todos los dropdowns...');
        
        dropdownButtons.forEach(function(button) {
            const targetId = button.getAttribute('aria-controls');
            if (targetId) {
                const dropdown = document.getElementById(targetId);
                const arrow = button.querySelector('.arrow');
                
                if (dropdown && !dropdown.classList.contains('hidden')) {
                    dropdown.classList.add('hidden');
                    if (arrow) {
                        arrow.style.transform = 'rotate(0deg)';
                    }
                }
            }
        });
    }
    
    // Función para reinicializar si es necesario
    function reinitialize() {
        if (isInitialized) {
            console.log('🔄 Reinicializando sidebar...');
            isInitialized = false;
        }
        return initializeSidebar();
    }
    
    // Intentar inicializar cuando el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeSidebar);
    } else {
        // DOM ya está listo
        setTimeout(initializeSidebar, 100);
    }
    
    // También intentar después de que la página esté completamente cargada
    window.addEventListener('load', function() {
        if (!isInitialized) {
            console.log('🔄 Intentando inicializar después de window.load...');
            setTimeout(initializeSidebar, 200);
        }
    });
    
    // Exponer funciones globalmente para debugging
    window.sidebarDebug = {
        reinitialize: reinitialize,
        status: function() {
            return {
                initialized: isInitialized,
                buttonsFound: dropdownButtons.length,
                buttons: dropdownButtons
            };
        },
        closeAll: closeAllDropdowns
    };
    
    console.log('🎉 sidebar.js cargado completamente');
})();
