/*
 * @article: https://blog.positive.com/predicting-random-numbers-in-ethereum-smart-contracts-e5358c6b8620
 * @source: https://etherscan.io/address/0xa65d59708838581520511d98fb8b5d1f76a96cad#code
 * @vulnerable_at_lines: 17,19,21
 * @author: -
 */

 pragma solidity ^0.4.9;

library Deck {
	// returns random number from 0 to 51
	// let's say 'value' % 4 means suit (0 - Hearts, 1 - Spades, 2 - Diamonds, 3 - Clubs)
	//			 'value' / 4 means: 0 - King, 1 - Ace, 2 - 10 - pip values, 11 - Jacket, 12 - Queen

	function deal(address player, uint8 cardNumber) internal returns (uint8) {
		// <yes> <report> BAD_RANDOMNESS
		uint b = block.number;
		// <yes> <report> BAD_RANDOMNESS
		uint timestamp = block.timestamp;
		// <yes> <report> BAD_RANDOMNESS
		return uint8(uint256(keccak256(block.blockhash(b), player, cardNumber, timestamp)) % 52);
	}

	function valueOf(uint8 card, bool isBigAce) internal constant returns (uint8) {
		uint8 value = card / 4;
		if (value == 0 || value == 11 || value == 12) { // Face cards
			return 10;
		}
		if (value == 1 && isBigAce) { // Ace is worth 11
			return 11;
		}
		return value;
	}

	function isAce(uint8 card) internal constant returns (bool) {
		return card / 4 == 1;
	}

	function isTen(uint8 card) internal constant returns (bool) {
		return card / 4 == 10;
	}
}


contract BlackJack {
	using Deck for *;

	uint public minBet = 50 finney; // 0.05 eth
	uint public maxBet = 5 ether;

	uint8 BLACKJACK = 21;

  enum GameState { Ongoing, Player, Tie, House }

	struct Game {
		address player; // address игрока
		uint bet; // стывка

		uint8[] houseCards; // карты диллера
		uint8[] playerCards; // карты игрока

		GameState state; // состояние
		uint8 cardsDealt;
	}

	mapping (address => Game) public games;

	// Commit-reveal randomness state
	mapping(address => bytes32) public commitments; // commit(hash(seed))
	mapping(address => uint256) public revealedSeeds; // revealed seed (preimage)
	mapping(address => uint256) public gameSeeds; // seed locked for active game

	// reentrancy mutex
	bool private _locked;

	modifier gameIsGoingOn() {
		if (games[msg.sender].player == 0 || games[msg.sender].state != GameState.Ongoing) {
			throw; // game doesn't exist or already finished
		}
		_;
	}

	event Deal(
        bool isUser,
        uint8 _card
    );

    event GameStatus(
    	uint8 houseScore,
    	uint8 houseScoreBig,
    	uint8 playerScore,
    	uint8 playerScoreBig
    );

    event Log(
    	uint8 value
    );

	function BlackJack() {

	}

	function () payable {

	}

	// Commit phase: player commits keccak256(seed)
	function commit(bytes32 h) public {
		commitments[msg.sender] = h;
	}

	// Reveal phase: player reveals seed whose keccak256 matches their commitment
	function reveal(uint256 seed) public {
		if (commitments[msg.sender] == bytes32(0)) {
			throw;
		}
		if (keccak256(seed) != commitments[msg.sender]) {
			throw;
		}
		revealedSeeds[msg.sender] = seed;
		commitments[msg.sender] = bytes32(0);
	}

	// draws a card deterministically from the per-game seed (set when game started)
	function drawCard(address player, uint8 cardNumber) internal returns (uint8) {
		if (gameSeeds[player] == 0) {
			// no seed available for this player's active game
			throw;
		}
		return uint8(uint256(keccak256(gameSeeds[player], player, cardNumber)) % 52);
	}

	// starts a new game
	function deal() public payable {
		// reentrancy guard
		require(!_locked);
		_locked = true;

		if (games[msg.sender].player != 0 && games[msg.sender].state == GameState.Ongoing) {
			_locked = false;
			throw; // game is already going on
		}

		if (msg.value < minBet || msg.value > maxBet) {
			_locked = false;
			throw; // incorrect bet
		}

		// Player must have revealed a seed before starting the game (commit-reveal)
		if (revealedSeeds[msg.sender] == 0) {
			_locked = false;
			throw; // randomness seed not revealed
		}

		// lock the seed for this game and clear the revealed one so it can't be reused
		gameSeeds[msg.sender] = revealedSeeds[msg.sender];
		revealedSeeds[msg.sender] = 0;

		uint8[] memory houseCards = new uint8[](1);
		uint8[] memory playerCards = new uint8[](2);

		// deal the cards using the committed seed (drawCard uses gameSeeds)
		playerCards[0] = drawCard(msg.sender, 0);
		Deal(true, playerCards[0]);
		houseCards[0] = drawCard(msg.sender, 1);
		Deal(false, houseCards[0]);
		playerCards[1] = drawCard(msg.sender, 2);
		Deal(true, playerCards[1]);

		games[msg.sender] = Game({
			player: msg.sender,
			bet: msg.value,
			houseCards: houseCards,
			playerCards: playerCards,
			state: GameState.Ongoing,
			cardsDealt: 3
		});

		checkGameResult(games[msg.sender], false);

		_locked = false;
	}

	// deals one more card to the player
	function hit() public gameIsGoingOn {
		// reentrancy guard
		require(!_locked);
		_locked = true;

		uint8 nextCard = games[msg.sender].cardsDealt;
		// draw using per-game seed
		games[msg.sender].playerCards.push(drawCard(msg.sender, nextCard));
		games[msg.sender].cardsDealt = nextCard + 1;
		Deal(true, games[msg.sender].playerCards[games[msg.sender].playerCards.length - 1]);
		checkGameResult(games[msg.sender], false);

		_locked = false;
	}

	// finishes the game
	function stand() public gameIsGoingOn {

		// reentrancy guard
		require(!_locked);
		_locked = true;

		var (houseScore, houseScoreBig) = calculateScore(games[msg.sender].houseCards);

		while (houseScoreBig < 17) {
			uint8 nextCard = games[msg.sender].cardsDealt;
			uint8 newCard = drawCard(msg.sender, nextCard);
			games[msg.sender].houseCards.push(newCard);
			games[msg.sender].cardsDealt = nextCard + 1;
			houseScoreBig += Deck.valueOf(newCard, true);
			Deal(false, newCard);
		}

		checkGameResult(games[msg.sender], true);

		_locked = false;
	}

	// @param finishGame - whether to finish the game or not (in case of Blackjack the game finishes anyway)
	function checkGameResult(Game game, bool finishGame) private {
		// calculate house score
		var (houseScore, houseScoreBig) = calculateScore(game.houseCards);
		// calculate player score
		var (playerScore, playerScoreBig) = calculateScore(game.playerCards);

		GameStatus(houseScore, houseScoreBig, playerScore, playerScoreBig);

		if (houseScoreBig == BLACKJACK || houseScore == BLACKJACK) {
			if (playerScore == BLACKJACK || playerScoreBig == BLACKJACK) {
				// TIE
				games[msg.sender].state = GameState.Tie; // finish the game
				// clear per-game seed
				gameSeeds[msg.sender] = 0;
				require(msg.sender.send(game.bet)); // return bet to the player
				return;
			} else {
				// HOUSE WON
				games[msg.sender].state = GameState.House; // simply finish the game
				// clear per-game seed
				gameSeeds[msg.sender] = 0;
				return;
			}
		} else {
			if (playerScore == BLACKJACK || playerScoreBig == BLACKJACK) {
				// PLAYER WON
				if (game.playerCards.length == 2 && (Deck.isTen(game.playerCards[0]) || Deck.isTen(game.playerCards[1]))) {
					// Natural blackjack => return x2.5
					games[msg.sender].state = GameState.Player; // finish the game
					// clear per-game seed
					gameSeeds[msg.sender] = 0;
					require(msg.sender.send((game.bet * 5) / 2)); // send prize to the player
				} else {
					// Usual blackjack => return x2
					games[msg.sender].state = GameState.Player; // finish the game
					// clear per-game seed
					gameSeeds[msg.sender] = 0;
					require(msg.sender.send(game.bet * 2)); // send prize to the player
				}
				return;
			} else {

				if (playerScore > BLACKJACK) {
					// BUST, HOUSE WON
					Log(1);
					games[msg.sender].state = GameState.House; // finish the game
					// clear per-game seed
					gameSeeds[msg.sender] = 0;
					return;
				}

				if (!finishGame) {
					return; // continue the game
				}

                // недобор
				uint8 playerShortage = 0;
				uint8 houseShortage = 0;

				// player decided to finish the game
				if (playerScoreBig > BLACKJACK) {
					if (playerScore > BLACKJACK) {
						// HOUSE WON
						games[msg.sender].state = GameState.House; // simply finish the game
						// clear per-game seed
						gameSeeds[msg.sender] = 0;
						return;
					} else {
						playerShortage = BLACKJACK - playerScore;
					}
				} else {
					playerShortage = BLACKJACK - playerScoreBig;
				}

				if (houseScoreBig > BLACKJACK) {
					if (houseScore > BLACKJACK) {
						// PLAYER WON
						games[msg.sender].state = GameState.Player;
						// clear per-game seed
						gameSeeds[msg.sender] = 0;
						require(msg.sender.send(game.bet * 2)); // send prize to the player
						return;
					} else {
						houseShortage = BLACKJACK - houseScore;
					}
				} else {
					houseShortage = BLACKJACK - houseScoreBig;
				}

                // ?????????????????????? почему игра заканчивается?
				if (houseShortage == playerShortage) {
					// TIE
					games[msg.sender].state = GameState.Tie;
					// clear per-game seed
					gameSeeds[msg.sender] = 0;
					require(msg.sender.send(game.bet)); // return bet to the player
				} else if (houseShortage > playerShortage) {
					// PLAYER WON
					games[msg.sender].state = GameState.Player;
					// clear per-game seed
					gameSeeds[msg.sender] = 0;
					require(msg.sender.send(game.bet * 2)); // send prize to the player
				} else {
					games[msg.sender].state = GameState.House;
					// clear per-game seed
					gameSeeds[msg.sender] = 0;
				}
			}
		}
	}

	function calculateScore(uint8[] cards) private constant returns (uint8, uint8) {
		uint8 score = 0;
		uint8 scoreBig = 0; // in case of Ace there could be 2 different scores
		bool bigAceUsed = false;
		for (uint i = 0; i < cards.length; ++i) {
			uint8 card = cards[i];
			if (Deck.isAce(card) && !bigAceUsed) { // doesn't make sense to use the second Ace as 11, because it leads to the losing
				scoreBig += Deck.valueOf(card, true);
				bigAceUsed = true;
			} else {
				scoreBig += Deck.valueOf(card, false);
			}
			score += Deck.valueOf(card, false);
		}
		return (score, scoreBig);
	}

	function getPlayerCard(uint8 id) public gameIsGoingOn constant returns(uint8) {
		if (id < 0 || id > games[msg.sender].playerCards.length) {
			throw;
		}
		return games[msg.sender].playerCards[id];
	}

	function getHouseCard(uint8 id) public gameIsGoingOn constant returns(uint8) {
		if (id < 0 || id > games[msg.sender].houseCards.length) {
			throw;
		}
		return games[msg.sender].houseCards[id];
	}

	function getPlayerCardsNumber() public gameIsGoingOn constant returns(uint) {
		return games[msg.sender].playerCards.length;
	}

	function getHouseCardsNumber() public gameIsGoingOn constant returns(uint) {
		return games[msg.sender].houseCards.length;
	}

	function getGameState() public constant returns (uint8) {
		if (games[msg.sender].player == 0) {
			throw; // game doesn't exist
		}

		Game game = games[msg.sender];

		if (game.state == GameState.Player) {
			return 1;
		}
		if (game.state == GameState.House) {
			return 2;
		}
		if (game.state == GameState.Tie) {
			return 3;
		}

		return 0; // the game is still going on
	}

}
