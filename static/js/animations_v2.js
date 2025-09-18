/**
 * Animations & Feedback v2.0 - Sistema de Animações e Feedback Visual
 * Melhora a experiência do usuário com animações fluidas e feedback visual
 */

class AnimationsV2 {
    constructor() {
        this.observers = new Map();
        this.animations = new Map();
        this.notificationQueue = [];
        this.isShowingNotification = false;
        this.init();
    }

    async init() {
        console.log('✨ Inicializando Animations v2.0');
        
        // Configurar observadores de elementos
        this.setupIntersectionObservers();
        
        // Configurar animações automáticas
        this.setupAutoAnimations();
        
        // Configurar transições de página
        this.setupPageTransitions();
        
        // Configurar feedback de loading
        this.setupLoadingFeedback();
        
        console.log('✅ Animations v2.0 inicializado');
    }

    // ===== OBSERVADORES DE ELEMENTOS =====
    setupIntersectionObservers() {
        // Observer para cards animados
        const cardObserver = new IntersectionObserver(
            (entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        this.animateCard(entry.target);
                    }
                });
            },
            { threshold: 0.1, rootMargin: '0px 0px -50px 0px' }
        );

        // Observer para contadores
        const counterObserver = new IntersectionObserver(
            (entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        this.animateCounter(entry.target);
                    }
                });
            },
            { threshold: 0.5 }
        );

        // Aplicar observers
        this.applyObservers(cardObserver, counterObserver);
    }

    applyObservers(cardObserver, counterObserver) {
        // Cards animados
        document.querySelectorAll('.card, [data-animate="card"]').forEach(card => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(30px)';
            card.style.transition = 'all 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
            cardObserver.observe(card);
        });

        // Contadores
        document.querySelectorAll('[data-stat], [data-counter]').forEach(counter => {
            counterObserver.observe(counter);
        });

        this.observers.set('cards', cardObserver);
        this.observers.set('counters', counterObserver);
    }

    // ===== ANIMAÇÕES DE ELEMENTOS =====
    animateCard(element) {
        element.style.opacity = '1';
        element.style.transform = 'translateY(0)';
        
        // Adicionar efeito de brilho sutil
        element.classList.add('animate-fade-in');
        
        // Remover classe após animação
        setTimeout(() => {
            element.classList.remove('animate-fade-in');
        }, 600);
    }

    animateCounter(element) {
        const finalValue = element.textContent.trim();
        const isMonetary = finalValue.includes('R$');
        const isCurrency = finalValue.includes(',');
        
        // Extrair número
        let targetValue = finalValue.replace(/[^\d,.-]/g, '');
        if (isCurrency) {
            targetValue = parseFloat(targetValue.replace(',', '.'));
        } else {
            targetValue = parseInt(targetValue) || 0;
        }
        
        if (targetValue === 0) return;

        // Animar contador
        this.animateCounterValue(element, 0, targetValue, 1000, isMonetary);
    }

    animateCounterValue(element, start, end, duration, isMonetary = false) {
        const startTime = performance.now();
        
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Easing function (easeOutQuart)
            const easeProgress = 1 - Math.pow(1 - progress, 4);
            
            const currentValue = start + (end - start) * easeProgress;
            
            if (isMonetary) {
                const formatted = this.formatCurrency(currentValue);
                element.textContent = formatted;
            } else {
                element.textContent = Math.floor(currentValue).toLocaleString('pt-BR');
            }
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }

    // ===== ANIMAÇÕES AUTOMÁTICAS =====
    setupAutoAnimations() {
        // Pulso para elementos importantes
        document.querySelectorAll('[data-pulse]').forEach(element => {
            this.addPulseAnimation(element);
        });

        // Hover effects aprimorados
        document.querySelectorAll('button, .btn, [data-button]').forEach(button => {
            this.enhanceButtonAnimations(button);
        });

        // Loading spinners
        document.querySelectorAll('[data-loading]').forEach(loader => {
            this.setupLoadingSpinner(loader);
        });
    }

    addPulseAnimation(element) {
        element.classList.add('animate-pulse-subtle');
        
        // Parar animação ao interagir
        element.addEventListener('mouseenter', () => {
            element.classList.remove('animate-pulse-subtle');
        });
        
        element.addEventListener('mouseleave', () => {
            element.classList.add('animate-pulse-subtle');
        });
    }

    enhanceButtonAnimations(button) {
        // Adicionar classes CSS customizadas
        button.classList.add('btn-animated');
        
        // Efeito ripple no click
        button.addEventListener('click', (e) => {
            this.createRippleEffect(e, button);
        });
        
        // Micro-animations de hover
        button.addEventListener('mouseenter', () => {
            button.style.transform = 'translateY(-1px)';
        });
        
        button.addEventListener('mouseleave', () => {
            button.style.transform = 'translateY(0)';
        });
    }

    createRippleEffect(event, element) {
        const ripple = document.createElement('span');
        const rect = element.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = event.clientX - rect.left - size / 2;
        const y = event.clientY - rect.top - size / 2;
        
        ripple.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            left: ${x}px;
            top: ${y}px;
            background: rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            transform: scale(0);
            animation: ripple 0.6s linear;
            pointer-events: none;
        `;
        
        element.style.position = 'relative';
        element.style.overflow = 'hidden';
        element.appendChild(ripple);
        
        setTimeout(() => {
            ripple.remove();
        }, 600);
    }

    // ===== NOTIFICAÇÕES ANIMADAS =====
    async showNotification(message, type = 'info', duration = 4000) {
        const notification = {
            id: this.generateId(),
            message,
            type,
            duration,
            element: null
        };
        
        this.notificationQueue.push(notification);
        this.processNotificationQueue();
    }

    async processNotificationQueue() {
        if (this.isShowingNotification || this.notificationQueue.length === 0) return;
        
        this.isShowingNotification = true;
        const notification = this.notificationQueue.shift();
        
        await this.displayNotification(notification);
        
        this.isShowingNotification = false;
        
        // Processar próxima notificação
        if (this.notificationQueue.length > 0) {
            setTimeout(() => this.processNotificationQueue(), 300);
        }
    }

    async displayNotification(notification) {
        return new Promise((resolve) => {
            const element = this.createNotificationElement(notification);
            notification.element = element;
            
            document.body.appendChild(element);
            
            // Animação de entrada
            requestAnimationFrame(() => {
                element.style.transform = 'translateX(0) translateY(0)';
                element.style.opacity = '1';
            });
            
            // Auto-remover após duration
            setTimeout(() => {
                this.hideNotification(notification, resolve);
            }, notification.duration);
            
            // Click para remover
            element.addEventListener('click', () => {
                this.hideNotification(notification, resolve);
            });
        });
    }

    createNotificationElement(notification) {
        const element = document.createElement('div');
        const typeColors = {
            success: 'bg-green-600 border-green-500',
            error: 'bg-red-600 border-red-500',
            warning: 'bg-yellow-600 border-yellow-500',
            info: 'bg-blue-600 border-blue-500'
        };
        
        const typeIcons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️'
        };
        
        element.className = `
            fixed top-4 right-4 z-50 p-4 rounded-lg shadow-2xl border-l-4 
            ${typeColors[notification.type] || typeColors.info}
            text-white cursor-pointer transform transition-all duration-500 ease-out
            translate-x-full opacity-0 max-w-md
        `.replace(/\s+/g, ' ').trim();
        
        element.innerHTML = `
            <div class="flex items-start space-x-3">
                <span class="text-xl flex-shrink-0 mt-0.5">
                    ${typeIcons[notification.type] || typeIcons.info}
                </span>
                <div class="flex-1">
                    <div class="text-sm font-medium">
                        ${notification.message}
                    </div>
                    <div class="text-xs opacity-75 mt-1">
                        Clique para fechar
                    </div>
                </div>
                <button class="text-white hover:text-gray-200 text-lg leading-none">
                    ×
                </button>
            </div>
        `;
        
        return element;
    }

    hideNotification(notification, callback) {
        if (!notification.element) return;
        
        notification.element.style.transform = 'translateX(100%) translateY(-10px)';
        notification.element.style.opacity = '0';
        
        setTimeout(() => {
            if (notification.element && notification.element.parentNode) {
                notification.element.remove();
            }
            callback && callback();
        }, 500);
    }

    // ===== TRANSIÇÕES DE PÁGINA =====
    setupPageTransitions() {
        // Transições suaves entre páginas
        document.addEventListener('click', (e) => {
            const link = e.target.closest('a[href]');
            if (link && link.hostname === location.hostname && !link.hasAttribute('data-no-transition')) {
                this.handlePageTransition(e, link);
            }
        });
        
        // Animação de entrada da página
        this.animatePageEntrance();
    }

    handlePageTransition(event, link) {
        if (link.href === location.href) return;
        
        event.preventDefault();
        
        // Adicionar overlay de transição
        const overlay = this.createTransitionOverlay();
        document.body.appendChild(overlay);
        
        // Animar saída
        requestAnimationFrame(() => {
            overlay.style.opacity = '1';
            document.body.style.transform = 'scale(0.98)';
            document.body.style.opacity = '0.7';
        });
        
        // Navegar após animação
        setTimeout(() => {
            window.location.href = link.href;
        }, 300);
    }

    createTransitionOverlay() {
        const overlay = document.createElement('div');
        overlay.className = 'page-transition-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(16, 185, 129, 0.1));
            backdrop-filter: blur(8px);
            z-index: 9999;
            opacity: 0;
            transition: opacity 0.3s ease-out;
            pointer-events: none;
        `;
        return overlay;
    }

    animatePageEntrance() {
        document.body.style.opacity = '0';
        document.body.style.transform = 'translateY(20px)';
        
        requestAnimationFrame(() => {
            document.body.style.transition = 'all 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
            document.body.style.opacity = '1';
            document.body.style.transform = 'translateY(0)';
        });
    }

    // ===== LOADING E FEEDBACK =====
    setupLoadingFeedback() {
        // Interceptar formulários para mostrar loading
        document.addEventListener('submit', (e) => {
            const form = e.target;
            if (form.tagName === 'FORM') {
                this.showFormLoading(form);
            }
        });
        
        // Interceptar botões com data-loading
        document.querySelectorAll('[data-loading-text]').forEach(button => {
            button.addEventListener('click', () => {
                this.showButtonLoading(button);
            });
        });
    }

    showFormLoading(form) {
        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitBtn) {
            this.showButtonLoading(submitBtn);
        }
        
        // Adicionar spinner ao formulário
        const spinner = this.createLoadingSpinner();
        form.appendChild(spinner);
    }

    showButtonLoading(button) {
        if (button.dataset.loading === 'true') return;
        
        const originalText = button.textContent;
        const loadingText = button.dataset.loadingText || 'Carregando...';
        
        button.dataset.loading = 'true';
        button.dataset.originalText = originalText;
        button.disabled = true;
        
        // Adicionar spinner
        button.innerHTML = `
            <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            ${loadingText}
        `;
    }

    hideButtonLoading(button) {
        if (button.dataset.loading !== 'true') return;
        
        const originalText = button.dataset.originalText || 'Botão';
        
        button.dataset.loading = 'false';
        button.disabled = false;
        button.textContent = originalText;
    }

    createLoadingSpinner(size = 'medium') {
        const spinner = document.createElement('div');
        const sizeClasses = {
            small: 'w-4 h-4',
            medium: 'w-8 h-8',
            large: 'w-12 h-12'
        };
        
        spinner.className = `
            inline-block ${sizeClasses[size]} 
            border-4 border-gray-300 border-t-blue-600 
            rounded-full animate-spin
        `.replace(/\s+/g, ' ').trim();
        
        return spinner;
    }

    // ===== ANIMAÇÕES DE VALORES =====
    animateValue(element, startValue, endValue, duration = 1000, formatter = null) {
        const startTime = performance.now();
        
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Easing function
            const easeProgress = progress < 0.5 
                ? 2 * progress * progress 
                : 1 - Math.pow(-2 * progress + 2, 2) / 2;
            
            const currentValue = startValue + (endValue - startValue) * easeProgress;
            
            if (formatter) {
                element.textContent = formatter(currentValue);
            } else {
                element.textContent = Math.floor(currentValue);
            }
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }

    // ===== UTILITÁRIOS =====
    formatCurrency(value) {
        return (value / 100).toLocaleString('pt-BR', {
            style: 'currency',
            currency: 'BRL'
        });
    }

    generateId() {
        return Math.random().toString(36).substr(2, 9);
    }

    // ===== MÉTODOS PÚBLICOS =====
    pulse(element, duration = 1000) {
        element.style.animation = `pulse ${duration}ms ease-in-out`;
        setTimeout(() => {
            element.style.animation = '';
        }, duration);
    }

    bounce(element) {
        element.style.animation = 'bounce 0.6s ease-in-out';
        setTimeout(() => {
            element.style.animation = '';
        }, 600);
    }

    shake(element) {
        element.style.animation = 'shake 0.5s ease-in-out';
        setTimeout(() => {
            element.style.animation = '';
        }, 500);
    }

    highlight(element, color = '#3B82F6') {
        const originalBackground = element.style.backgroundColor;
        element.style.backgroundColor = color;
        element.style.transition = 'background-color 0.3s ease';
        
        setTimeout(() => {
            element.style.backgroundColor = originalBackground;
        }, 300);
    }

    // ===== LIMPEZA =====
    destroy() {
        // Limpar observers
        this.observers.forEach(observer => observer.disconnect());
        this.observers.clear();
        
        // Limpar animações
        this.animations.clear();
        
        // Limpar notificações
        this.notificationQueue.forEach(notification => {
            if (notification.element) {
                notification.element.remove();
            }
        });
        this.notificationQueue = [];
        
        console.log('🗑️ Animations v2.0 destruído');
    }
}

// Instância global
window.animationsV2 = null;

// CSS Animations (injetadas dinamicamente)
const cssAnimations = `
    <style>
    @keyframes ripple {
        to {
            transform: scale(4);
            opacity: 0;
        }
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
    }
    
    @keyframes bounce {
        0%, 20%, 53%, 80%, 100% { transform: translateY(0); }
        40%, 43% { transform: translateY(-10px); }
        70% { transform: translateY(-5px); }
        90% { transform: translateY(-2px); }
    }
    
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-5px); }
        50% { transform: translateX(5px); }
        75% { transform: translateX(-5px); }
    }
    
    .animate-pulse-subtle {
        animation: pulse 2s infinite ease-in-out;
    }
    
    .animate-fade-in {
        animation: fadeIn 0.6s ease-out;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .btn-animated {
        transition: all 0.2s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        position: relative;
        overflow: hidden;
    }
    
    .btn-animated:active {
        transform: translateY(1px);
    }
    </style>
`;

// Inicializar quando a página carregar
document.addEventListener('DOMContentLoaded', () => {
    // Injetar CSS
    document.head.insertAdjacentHTML('beforeend', cssAnimations);
    
    // Inicializar animations
    window.animationsV2 = new AnimationsV2();
    
    console.log('✨ Animations v2.0 disponível globalmente como window.animationsV2');
    
    // Exemplo de uso para notificações
    window.showNotification = (message, type, duration) => {
        if (window.animationsV2) {
            window.animationsV2.showNotification(message, type, duration);
        }
    };
});

// Limpeza ao sair da página
window.addEventListener('beforeunload', () => {
    if (window.animationsV2) {
        window.animationsV2.destroy();
    }
});

// Exportar para uso em módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AnimationsV2;
}
