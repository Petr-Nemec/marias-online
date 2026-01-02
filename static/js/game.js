/**
 * Mariáš Online v3.0 - SPRÁVNÁ PRAVIDLA
 * 
 * KRITICKÉ OPRAVY:
 * - Hlášky: Svršek (Q) + Král (K)
 * - Desítka je DRUHÁ nejsilnější
 * - Pořadí: 7-8-9-spodek-svršek-král-10-A
 */

class MariaClient {
    constructor() {
        this.socket = null;
        this.state = {
            sessionId: null,
            gameState: null,
            isPlayer: false,
            selectedCardsForDiscard: [],
            selectedTrumpSuit: null,
            isLoading: false
        };
        
        // SPRÁVNÉ názvy podle českých karet
        this.SUIT_SYMBOLS = {
            hearts: '♥',
            diamonds: '♦',
            clubs: '♣',
            spades: '♠'
        };
        
        this.SUIT_NAMES = {
            hearts: 'Červené/Srdce',
            diamonds: 'Kule',
            clubs: 'Žaludy',
            spades: 'Zelené/Listy'
        };
        
        // SPRÁVNÉ názvy karet
        this.RANK_NAMES = {
            '7': 'Sedma',
            '8': 'Osma',
            '9': 'Devítka',
            '10': 'Desítka',  // DRUHÁ nejsilnější!
            'J': 'Spodek',    // ← OPRAVENO!
            'Q': 'Svršek',    // ← OPRAVENO!
            'K': 'Král',
            'A': 'Eso'
        };
        
        // Typy her
        this.GAME_TYPES = {
            'hra': 'Hra',
            'sedma': 'Sedma',
            'sto': 'Sto',
            'betl': 'Betl',
            'durch': 'Durch'
        };
        
        this.PHASE_NAMES = {
            'waiting': 'Čekáme na hráče...',
            'bidding': 'Licitace',
            'playing': 'Hra probíhá',
            'round_end': 'Konec kola'
        };
    }
    
    // ========== INICIALIZACE ==========
    
    init() {
        this.initSocket();
        this.initEventListeners();
        console.log('✓ Mariáš Client v3.0 inicializován (SPRÁVNÁ PRAVIDLA)');
    }
    
    initSocket() {
        this.socket = io({
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionAttempts: 5
        });
        
        this.socket.on('connect', () => {
            console.log('✓ Připojeno k serveru v3.0');
            this.hideLoading();
        });
        
        this.socket.on('disconnect', () => {
            console.log('✗ Odpojeno od serveru');
            this.showMessage('Odpojeno od serveru', 'error');
            this.showLoading('Opětovné připojování...');
        });
        
        this.socket.on('connection_established', (data) => {
            this.state.sessionId = data.session_id;
            console.log('Session ID:', this.state.sessionId);
            console.log('Server version:', data.version);
        });
        
        this.socket.on('joined_game', this.handleJoinedGame.bind(this));
        this.socket.on('game_update', this.handleGameUpdate.bind(this));
        this.socket.on('bidding_complete', this.handleBiddingComplete.bind(this));
        this.socket.on('trick_complete', this.handleTrickComplete.bind(this));
        this.socket.on('round_complete', this.handleRoundComplete.bind(this));
        this.socket.on('chat_message', this.handleChatMessage.bind(this));
        this.socket.on('error', this.handleError.bind(this));
    }
    
    initEventListeners() {
        document.getElementById('player-name')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.joinGame();
        });
        
        document.getElementById('chat-input')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });
    }
    
    // ========== SOCKET HANDLERS ==========
    
    handleJoinedGame(data) {
        this.hideLoading();
        
        if (data.success) {
            this.state.isPlayer = data.is_player;
            this.showGameScreen();
            this.updateGameState(data.game_state);
            
            if (!this.state.isPlayer) {
                this.showMessage('Sledujete hru jako divák', 'info');
            }
        } else {
            this.showMessage(data.message || 'Nelze se připojit', 'error');
        }
    }
    
    handleGameUpdate(data) {
        this.updateGameState(data.game_state);
        if (data.message) {
            this.showMessage(data.message, 'info');
        }
    }
    
    handleBiddingComplete(data) {
        console.log('Licitace dokončena');
    }
    
    handleTrickComplete(data) {
        const msg = `${data.winner_name} bere štych`;
        this.showMessage(msg, 'success');
    }
    
    handleRoundComplete(data) {
        this.showRoundResults(data.round_results);
    }
    
    handleChatMessage(data) {
        this.addChatMessage(data.player, data.message, data.timestamp);
    }
    
    handleError(data) {
        this.showMessage(data.message, 'error');
        this.hideLoading();
    }
    
    // ========== GAME ACTIONS ==========
    
    joinGame() {
        const nameInput = document.getElementById('player-name');
        const name = nameInput.value.trim();
        
        if (!name) {
            this.showMessage('Zadej své jméno', 'error');
            return;
        }
        
        if (name.length > 20) {
            this.showMessage('Jméno je příliš dlouhé (max 20 znaků)', 'error');
            return;
        }
        
        this.showLoading('Připojování...');
        this.socket.emit('join_game', { name });
    }
    
    bidGame(gameType) {
        if (this.state.isLoading) return;
        
        this.showLoading('Licitace...');
        this.socket.emit('bid_game', { game_type: gameType });
    }
    
    passBid() {
        if (this.state.isLoading) return;
        
        this.showLoading('Pasování...');
        this.socket.emit('pass_bid');
    }
    
    selectTrumpSuit(suit) {
        this.state.selectedTrumpSuit = suit;
        this.updateTrumpSelection();
    }
    
    confirmTrumpAndDiscard() {
        if (!this.state.selectedTrumpSuit) {
            this.showMessage('Musíš vybrat trumf', 'error');
            return;
        }
        
        if (this.state.selectedCardsForDiscard.length !== 2) {
            this.showMessage('Vyber přesně 2 karty k odhození', 'error');
            return;
        }
        
        this.showLoading('Výběr trumfu...');
        this.socket.emit('select_trump_and_discard', {
            trump_suit: this.state.selectedTrumpSuit,
            cards: this.state.selectedCardsForDiscard
        });
        
        this.state.selectedCardsForDiscard = [];
        this.state.selectedTrumpSuit = null;
    }
    
    declareMarriage(suit) {
        if (this.state.isLoading) return;
        
        this.socket.emit('declare_marriage', { suit });
        this.hideMarriageSelection();
    }
    
    playCard(card) {
        if (this.state.isLoading) return;
        if (!this.state.gameState?.is_your_turn) return;
        
        this.showLoading('Hraní karty...');
        this.socket.emit('play_card', { card });
    }
    
    startNewRound() {
        this.hideRoundModal();
        this.socket.emit('start_new_round');
    }
    
    // ========== UI UPDATES ==========
    
    updateGameState(gameState) {
        this.state.gameState = gameState;
        this.hideLoading();
        
        if (!gameState) return;
        
        this.updatePhaseIndicator();
        this.updatePlayersList();
        this.updateScores();
        this.updateGameTable();
        
        if (this.state.isPlayer && gameState.hand) {
            this.updatePlayerHand();
        }
        
        this.updatePanelVisibility();
    }
    
    updatePhaseIndicator() {
        const indicator = document.getElementById('phase-indicator');
        if (!indicator) return;
        
        const phase = this.state.gameState.phase;
        indicator.textContent = this.PHASE_NAMES[phase] || phase;
        
        if (this.state.gameState.is_your_turn) {
            indicator.style.background = 'rgba(255, 193, 7, 0.3)';
            indicator.style.animation = 'pulse 1.5s infinite';
        } else {
            indicator.style.background = 'rgba(255,255,255,0.2)';
            indicator.style.animation = 'none';
        }
    }
    
    updatePlayersList() {
        const list = document.getElementById('players-list');
        if (!list) return;
        
        list.innerHTML = '';
        
        this.state.gameState.players.forEach(player => {
            const item = document.createElement('div');
            item.className = 'player-item';
            
            if (player.is_current) {
                item.classList.add('current-turn');
            }
            
            let badges = '';
            if (player.is_dealer) badges += ' 🎴';
            if (player.is_bidder) badges += ' 👑';
            if (!player.connected) badges += ' ⚠️';
            
            item.innerHTML = `
                <span class="player-name">${this.escapeHtml(player.name)}${badges}</span>
                <span class="player-info">
                    Karty: ${player.card_count} | Štychy: ${player.tricks_count}
                </span>
            `;
            
            list.appendChild(item);
        });
    }
    
    updateScores() {
        const list = document.getElementById('scores-list');
        if (!list) return;
        
        list.innerHTML = '';
        
        this.state.gameState.players.forEach(player => {
            const item = document.createElement('div');
            item.className = 'score-item';
            
            const scoreClass = player.total_score >= 0 ? 'positive' : 'negative';
            
            item.innerHTML = `
                <span>${this.escapeHtml(player.name)}</span>
                <span class="score-value ${scoreClass}">${player.total_score}</span>
            `;
            
            list.appendChild(item);
        });
    }
    
    updateGameTable() {
        const gs = this.state.gameState;
        
        // Game type info
        const bidInfo = document.getElementById('bid-info');
        if (bidInfo) {
            if (gs.current_game_type) {
                bidInfo.textContent = `Hra: ${this.GAME_TYPES[gs.current_game_type] || gs.current_game_type}`;
            } else {
                bidInfo.textContent = '';
            }
        }
        
        // Trump info
        const trumpInfo = document.getElementById('trump-info');
        if (trumpInfo) {
            if (gs.trump_suit) {
                const symbol = this.SUIT_SYMBOLS[gs.trump_suit];
                const name = this.SUIT_NAMES[gs.trump_suit];
                trumpInfo.innerHTML = `Trumf: ${symbol} ${name}`;
            } else {
                trumpInfo.textContent = '';
            }
        }
        
        // Current trick
        const trickArea = document.getElementById('trick-area');
        if (trickArea) {
            trickArea.innerHTML = '';
            
            gs.current_trick.forEach(trick => {
                const wrapper = document.createElement('div');
                wrapper.className = 'trick-card';
                
                const card = this.createCardElement(trick.card, false);
                wrapper.innerHTML = `
                    <div class="trick-card-player">${this.escapeHtml(trick.player_name)}</div>
                `;
                wrapper.appendChild(card);
                
                trickArea.appendChild(wrapper);
            });
        }
    }
    
    updatePlayerHand() {
        const handCards = document.getElementById('hand-cards');
        if (!handCards) return;
        
        handCards.innerHTML = '';
        
        const gs = this.state.gameState;
        if (!gs.hand) return;
        
        gs.hand.forEach(card => {
            const cardEl = this.createCardElement(card, true);
            
            // Clickable podle fáze
            if (gs.phase === 'playing' && gs.is_your_turn) {
                if (gs.needs_trump_and_discard) {
                    // Výběr karet k odhození
                    cardEl.onclick = () => this.toggleCardForDiscard(cardEl, card);
                    cardEl.style.cursor = 'pointer';
                } else {
                    // Normální hraní
                    cardEl.onclick = () => this.playCard(card);
                    cardEl.style.cursor = 'pointer';
                }
            } else {
                cardEl.classList.add('disabled');
            }
            
            handCards.appendChild(cardEl);
        });
    }
    
    updatePanelVisibility() {
        const gs = this.state.gameState;
        
        // Bidding panel
        const biddingPanel = document.getElementById('bidding-panel');
        if (biddingPanel) {
            if (gs.phase === 'bidding' && gs.is_your_turn) {
                this.showBiddingPanel();
            } else {
                biddingPanel.classList.add('hidden');
            }
        }
        
        // Trump selection and discard
        const trumpPanel = document.getElementById('trump-selection-panel');
        if (trumpPanel) {
            if (gs.needs_trump_and_discard) {
                trumpPanel.classList.remove('hidden');
                this.updateDiscardCount();
            } else {
                trumpPanel.classList.add('hidden');
            }
        }
        
        // Marriage button
        const marriageBtn = document.getElementById('marriage-btn');
        if (marriageBtn) {
            if (gs.phase === 'playing' && gs.is_your_turn && this.state.isPlayer && !gs.needs_trump_and_discard) {
                marriageBtn.style.display = 'inline-block';
            } else {
                marriageBtn.style.display = 'none';
            }
        }
    }
    
    // ========== BIDDING ==========
    
    showBiddingPanel() {
        const panel = document.getElementById('bidding-panel');
        const buttons = document.getElementById('bid-buttons');
        
        if (!panel || !buttons) return;
        
        panel.classList.remove('hidden');
        buttons.innerHTML = '';
        
        // Typy her
        const gameTypes = [
            { type: 'hra', label: 'Hra', color: 'primary' },
            { type: 'sedma', label: 'Sedma', color: 'primary' },
            { type: 'sto', label: 'Sto', color: 'primary' },
            { type: 'betl', label: 'Betl', color: 'special' },
            { type: 'durch', label: 'Durch', color: 'special' }
        ];
        
        gameTypes.forEach(game => {
            const btn = document.createElement('button');
            btn.className = `bid-btn ${game.color}`;
            btn.textContent = game.label;
            btn.onclick = () => this.bidGame(game.type);
            buttons.appendChild(btn);
        });
    }
    
    // ========== TRUMP AND DISCARD ==========
    
    toggleCardForDiscard(cardEl, card) {
        const isSelected = cardEl.classList.contains('selected');
        
        if (isSelected) {
            cardEl.classList.remove('selected');
            this.state.selectedCardsForDiscard = this.state.selectedCardsForDiscard.filter(
                c => !(c.suit === card.suit && c.rank === card.rank)
            );
        } else {
            if (this.state.selectedCardsForDiscard.length < 2) {
                cardEl.classList.add('selected');
                this.state.selectedCardsForDiscard.push(card);
            } else {
                this.showMessage('Můžeš vybrat max 2 karty', 'warning');
            }
        }
        
        this.updateDiscardCount();
    }
    
    updateTrumpSelection() {
        // Update UI to show selected trump
        const buttons = document.querySelectorAll('.trump-select-btn');
        buttons.forEach(btn => {
            if (btn.dataset.suit === this.state.selectedTrumpSuit) {
                btn.classList.add('selected');
            } else {
                btn.classList.remove('selected');
            }
        });
        
        this.updateDiscardCount();
    }
    
    updateDiscardCount() {
        const countEl = document.getElementById('discard-count');
        const btn = document.getElementById('confirm-trump-discard');
        
        if (countEl) {
            countEl.textContent = `${this.state.selectedCardsForDiscard.length}/2`;
        }
        
        if (btn) {
            btn.disabled = this.state.selectedCardsForDiscard.length !== 2 || !this.state.selectedTrumpSuit;
        }
    }
    
    // ========== HELPERS ==========
    
    createCardElement(card, selectable = false) {
        const div = document.createElement('div');
        div.className = `card ${card.suit}`;
        
        // SPRÁVNÉ zobrazení
        const rankDisplay = card.rank;
        const suitSymbol = this.SUIT_SYMBOLS[card.suit];
        
        div.innerHTML = `
            <div class="card-rank">${rankDisplay}</div>
            <div class="card-suit">${suitSymbol}</div>
        `;
        
        // Tooltip se SPRÁVNÝMI názvy
        const rankName = this.RANK_NAMES[card.rank];
        const suitName = this.SUIT_NAMES[card.suit];
        div.title = `${rankName} ${suitName}`;
        
        if (selectable) {
            div.dataset.suit = card.suit;
            div.dataset.rank = card.rank;
        }
        
        return div;
    }
    
    // ========== UI HELPERS ==========
    
    showGameScreen() {
        document.getElementById('login-screen')?.classList.add('hidden');
        document.getElementById('game-screen')?.classList.remove('hidden');
    }
    
    showLoading(message = 'Načítání...') {
        this.state.isLoading = true;
    }
    
    hideLoading() {
        this.state.isLoading = false;
    }
    
    showMessage(text, type = 'info') {
        const container = document.getElementById('game-messages');
        if (!container) return;
        
        const msg = document.createElement('div');
        msg.className = `game-message ${type}`;
        msg.textContent = text;
        
        container.appendChild(msg);
        
        setTimeout(() => {
            msg.style.opacity = '0';
            setTimeout(() => msg.remove(), 300);
        }, 4000);
    }
    
    showRoundResults(results) {
        const modal = document.getElementById('round-modal');
        const resultsDiv = document.getElementById('round-results');
        
        if (!modal || !resultsDiv) return;
        
        resultsDiv.innerHTML = '';
        
        const sortedResults = Object.entries(results).sort((a, b) => {
            return b[1].total_score - a[1].total_score;
        });
        
        sortedResults.forEach(([playerId, data]) => {
            const player = this.state.gameState.players.find(p => p.id === playerId);
            if (!player) return;
            
            const item = document.createElement('div');
            item.className = 'result-item';
            
            if (data.is_bidder) {
                item.classList.add('bidder');
                if (data.success) {
                    item.classList.add('winner');
                } else {
                    item.classList.add('loser');
                }
            }
            
            item.innerHTML = `
                <div>
                    <strong>${this.escapeHtml(player.name)}</strong>
                    ${data.is_bidder ? (data.success ? '✅ Splněno' : '❌ Nesplněno') : ''}
                </div>
                <div>
                    <span>Kolo: ${data.round_score}</span>
                    <span class="score-value ${data.total_score >= 0 ? 'positive' : 'negative'}">
                        Celkem: ${data.total_score}
                    </span>
                </div>
            `;
            
            resultsDiv.appendChild(item);
        });
        
        modal.classList.remove('hidden');
    }
    
    hideRoundModal() {
        document.getElementById('round-modal')?.classList.add('hidden');
    }
    
    toggleChat() {
        document.getElementById('chat-panel')?.classList.toggle('hidden');
    }
    
    toggleMarriages() {
        document.getElementById('marriage-selection')?.classList.toggle('hidden');
    }
    
    hideMarriageSelection() {
        document.getElementById('marriage-selection')?.classList.add('hidden');
    }
    
    sendMessage() {
        const input = document.getElementById('chat-input');
        if (!input) return;
        
        const message = input.value.trim();
        
        if (message && message.length <= 200) {
            this.socket.emit('chat_message', { message });
            input.value = '';
        }
    }
    
    addChatMessage(player, message, timestamp) {
        const messages = document.getElementById('chat-messages');
        if (!messages) return;
        
        const msg = document.createElement('div');
        msg.className = 'chat-message';
        msg.innerHTML = `
            <div class="chat-message-player">
                ${this.escapeHtml(player)}
                <span class="chat-message-time">${timestamp}</span>
            </div>
            <div>${this.escapeHtml(message)}</div>
        `;
        
        messages.appendChild(msg);
        messages.scrollTop = messages.scrollHeight;
    }
    
    showRules() {
        const rules = `PRAVIDLA MARIÁŠE v3.0 (SPRÁVNÁ VERZE)

🃏 ZÁKLADY
• 32 karet: 7-8-9-10-spodek-svršek-král-eso
• 3 hráči
• Rozdání: 5-5-5-(2 talon)-5-5-5

💰 HODNOTY KARET
Eso (A) = 11 bodů
Desítka (10) = 10 bodů ← DRUHÁ nejsilnější!
Král (K) = 4 body
Svršek (Q) = 3 body
Spodek (J) = 2 body
9, 8, 7 = 0 bodů

📊 POŘADÍ SÍLY (s trumfy):
7 < 8 < 9 < spodek < svršek < král < 10 < A
(Desítka je DRUHÁ nejsilnější!)

🎯 LICITACE
Typy her (vzestupně):
• Hra - základní hra
• Sedma - poslední štych trumfovou sedmou
• Sto - získat minimálně 100 bodů
• Betl - nesmíš vzít ani jeden štych
• Durch - musíš vzít všechny štychy

🌟 HLÁŠKY (SVATBY)
SVRŠEK (Q) + KRÁL (K) stejné barvy!
• Normální barva = 20 bodů
• Trumf = 40 bodů (flék)

Hláška se provede položením první karty (Q nebo K) na své zdvihy.

⚡ PRAVIDLA HRY
1. Musíš přiznat barvu (pokud ji máš)
2. Pokud nemáš barvu → fleknout (trumf)
3. Pokud nemáš ani barvu ani trumf → cokoliv
4. Musíš přebíjet (pokud můžeš)

📋 TALON
Vítěz licitace:
1. Vezme si 2 karty z talonu
2. Odhodí 2 karty (nesmí esa a desítky!)
3. Body z odhozených karet získá

🏆 BODOVÁNÍ
Vítěz licitace splní svůj závazek → získá body
Nesplní → ztratí body
Ostatní hráči: podle varianty pravidel

Přeji příjemnou hru! 🎉`;
        
        alert(rules);
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Inicializace při načtení stránky
document.addEventListener('DOMContentLoaded', () => {
    window.mariaClient = new MariaClient();
    window.mariaClient.init();
});

// Export funkcí pro HTML onclick handlers
function joinGame() {
    window.mariaClient.joinGame();
}

function bidGame(type) {
    window.mariaClient.bidGame(type);
}

function passBid() {
    window.mariaClient.passBid();
}

function selectTrumpSuit(suit) {
    window.mariaClient.selectTrumpSuit(suit);
}

function confirmTrumpAndDiscard() {
    window.mariaClient.confirmTrumpAndDiscard();
}

function declareMarriage(suit) {
    window.mariaClient.declareMarriage(suit);
}

function startNewRound() {
    window.mariaClient.startNewRound();
}

function toggleChat() {
    window.mariaClient.toggleChat();
}

function toggleMarriages() {
    window.mariaClient.toggleMarriages();
}

function sendMessage() {
    window.mariaClient.sendMessage();
}

function showRules() {
    window.mariaClient.showRules();
}