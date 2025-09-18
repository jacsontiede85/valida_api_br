/**
 * Utilidades de autenticação compartilhadas
 */

class AuthUtils {
    
    /**
     * Obter token JWT do localStorage
     */
    static getAuthToken() {
        const authToken = localStorage.getItem('auth_token');
        const sessionToken = localStorage.getItem('session_token');
        
        // Priorizar auth_token (JWT novo) sobre session_token (legacy)
        const token = authToken || sessionToken;
        
        // Verificar se o token parece ser um JWT (formato xxx.yyy.zzz)
        if (token && token.includes('.') && token.split('.').length === 3) {
            return token;
        } else if (token) {
            console.warn('❌ Token encontrado mas não é um JWT válido:', token.substring(0, 20) + '...');
            // Limpar tokens inválidos
            localStorage.removeItem('auth_token');
            localStorage.removeItem('session_token');
            localStorage.removeItem('api_key');
            return null;
        }
        
        return null;
    }
    
    /**
     * Fazer requisição autenticada
     */
    static async authenticatedFetch(url, options = {}) {
        const token = this.getAuthToken();
        
        if (!token) {
            console.error('❌ Nenhum token JWT válido - redirecionando para login');
            window.location.href = '/login';
            throw new Error('Não autenticado');
        }
        
        // Configurar headers padrão com autenticação
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        };
        
        // Mesclar opções fornecidas com as padrão
        const finalOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...(options.headers || {})
            }
        };
        
        try {
            const response = await fetch(url, finalOptions);
            
            // Se 401, redirecionar para login
            if (response.status === 401) {
                console.error('❌ Token expirado ou inválido - redirecionando para login');
                localStorage.removeItem('auth_token');
                localStorage.removeItem('session_token');
                window.location.href = '/login';
                throw new Error('Token expirado');
            }
            
            return response;
        } catch (error) {
            console.error('❌ Erro na requisição autenticada:', error);
            throw error;
        }
    }
    
    /**
     * Fazer requisição autenticada e retornar JSON
     */
    static async authenticatedFetchJSON(url, options = {}) {
        const response = await this.authenticatedFetch(url, options);
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        
        return await response.json();
    }
    
    /**
     * Verificar se o usuário está autenticado
     */
    static isAuthenticated() {
        return this.getAuthToken() !== null;
    }
    
    /**
     * Fazer logout
     */
    static logout() {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('session_token');
        localStorage.removeItem('api_key');
        localStorage.removeItem('user_email');
        window.location.href = '/login';
    }
}

// Tornar disponível globalmente
window.AuthUtils = AuthUtils;
