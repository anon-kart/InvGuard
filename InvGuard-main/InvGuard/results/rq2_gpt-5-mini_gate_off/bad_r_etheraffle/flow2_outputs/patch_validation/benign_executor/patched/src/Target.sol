/*
 * @article: https://blog.positive.com/predicting-random-numbers-in-ethereum-smart-contracts-e5358c6b8620
 * @source: https://etherscan.io/address/0xcC88937F325d1C6B97da0AFDbb4cA542EFA70870#code
 * @vulnerable_at_lines: 49,99,101,103,114,158
 * @author: -
 */

 pragma solidity ^0.4.16;

contract Ethraffle_v4b {
    struct Contestant {
        address addr;
        uint raffleId;
    }

    event RaffleResult(
        uint raffleId,
        uint winningNumber,
        address winningAddress,
        address seed1,
        address seed2,
        uint seed3,
        bytes32 randHash
    );

    event TicketPurchase(
        uint raffleId,
        address contestant,
        uint number
    );

    event TicketRefund(
        uint raffleId,
        address contestant,
        uint number
    );

    // Constants
    uint public constant prize = 2.5 ether;
    uint public constant fee = 0.03 ether;
    uint public constant totalTickets = 50;
    uint public constant pricePerTicket = (prize + fee) / totalTickets; // Make sure this divides evenly
    address feeAddress;

    // Other internal variables
    bool public paused = false;
    uint public raffleId = 1;
    // <yes> <report> BAD_RANDOMNESS
    uint public blockNumber = block.number;
    uint nextTicket = 0;
    mapping (uint => Contestant) contestants;
    uint[] gaps;

    // New variables for commit/reveal injected randomness and reentrancy protection
    bool private _locked;
    bool public pending = false;
    bytes32 public randomSeed;
    uint public randomSeedBlock;
    uint public pendingRaffleId = 0;

    // Initialization
    function Ethraffle_v4b() public {
        feeAddress = msg.sender;
    }

    // Call buyTickets() when receiving Ether outside a function
    function () payable public {
        buyTickets();
    }

    function buyTickets() payable public {
        if (paused) {
            msg.sender.transfer(msg.value);
            return;
        }

        uint moneySent = msg.value;

        while (moneySent >= pricePerTicket && nextTicket < totalTickets) {
            uint currTicket = 0;
            if (gaps.length > 0) {
                currTicket = gaps[gaps.length-1];
                gaps.length--;
            } else {
                currTicket = nextTicket++;
            }

            contestants[currTicket] = Contestant(msg.sender, raffleId);
            TicketPurchase(raffleId, msg.sender, currTicket);
            moneySent -= pricePerTicket;
        }

        // Choose winner if we sold all the tickets
        if (nextTicket == totalTickets) {
            chooseWinner();
        }

        // Send back leftover money
        if (moneySent > 0) {
            msg.sender.transfer(moneySent);
        }
    }

    // Setter for injected randomness (only feeAddress can provide randomness)
    function submitRandomness(bytes32 seed) public {
        if (msg.sender == feeAddress) {
            randomSeed = seed;
            randomSeedBlock = block.number;
        }
    }

    // Anyone (or feeAddress) can finalize a pending raffle once randomness was set in a prior block
    function finalizeWinner() public {
        // Ensure a pending raffle exists
        require(pending);
        // randomSeed must be set and must have been set in a prior block (not the same block)
        require(randomSeed != 0 && randomSeedBlock < block.number);
        // Ensure raffle hasn't changed underneath us
        require(raffleId == pendingRaffleId);

        require(!_locked);
        _locked = true;

        // Compute randomness from injected seed and stable contract state (no block fields)
        bytes32 randHash = keccak256(randomSeed, address(this), pendingRaffleId);
        uint winningNumber = uint(randHash) % totalTickets;
        address winningAddress = contestants[winningNumber].addr;
        RaffleResult(pendingRaffleId, winningNumber, winningAddress, address(0), address(0), 0, randHash);

        // State updates before external calls (CEI)
        raffleId++;
        nextTicket = 0;
        blockNumber = block.number;
        // clear randomness and pending flag
        randomSeed = 0;
        randomSeedBlock = 0;
        pending = false;
        pendingRaffleId = 0;

        // Distribute prize and fee
        winningAddress.transfer(prize);
        feeAddress.transfer(fee);

        _locked = false;
    }

    function chooseWinner() private {
        // Reentrancy guard
        require(!_locked);
        _locked = true;

        // If there is no injected randomness set, or the randomness was set in the same block,
        // mark the raffle as pending and return so that randomness can be submitted in a later block
        if (randomSeed == 0 || randomSeedBlock >= block.number) {
            pending = true;
            pendingRaffleId = raffleId;
            // Do NOT change raffleId/nextTicket/blockNumber here; finalization will do that
            _locked = false;
            return;
        }

        // If randomness exists and was set in a prior block, use it immediately
        bytes32 randHash = keccak256(randomSeed, address(this), raffleId);
        uint winningNumber = uint(randHash) % totalTickets;
        address winningAddress = contestants[winningNumber].addr;
        RaffleResult(raffleId, winningNumber, winningAddress, address(0), address(0), 0, randHash);

        // Start next raffle - state updates before external calls (CEI)
        raffleId++;
        nextTicket = 0;
        blockNumber = block.number;
        // clear randomness
        randomSeed = 0;
        randomSeedBlock = 0;

        // Distribute prize and fee
        winningAddress.transfer(prize);
        feeAddress.transfer(fee);

        _locked = false;
    }

    // Get your money back before the raffle occurs
    function getRefund() public {
        uint refund = 0;
        for (uint i = 0; i < totalTickets; i++) {
            if (msg.sender == contestants[i].addr && raffleId == contestants[i].raffleId) {
                refund += pricePerTicket;
                contestants[i] = Contestant(address(0), 0);
                gaps.push(i);
                TicketRefund(raffleId, msg.sender, i);
            }
        }

        if (refund > 0) {
            msg.sender.transfer(refund);
        }
    }

    // Refund everyone's money, start a new raffle, then pause it
    function endRaffle() public {
        if (msg.sender == feeAddress) {
            paused = true;

            for (uint i = 0; i < totalTickets; i++) {
                if (raffleId == contestants[i].raffleId) {
                    TicketRefund(raffleId, contestants[i].addr, i);
                    contestants[i].addr.transfer(pricePerTicket);
                }
            }

            RaffleResult(raffleId, totalTickets, address(0), address(0), address(0), 0, 0);
            raffleId++;
            nextTicket = 0;
            // <yes> <report> BAD_RANDOMNESS
            blockNumber = block.number;
            gaps.length = 0;
        }
    }

    function togglePause() public {
        if (msg.sender == feeAddress) {
            paused = !paused;
        }
    }

    function kill() public {
        if (msg.sender == feeAddress) {
            selfdestruct(feeAddress);
        }
    }
}


// ---- auto-added by BenignExecutor ----
// Provides a stable deployable name used by the harness: `Target`.
// Assumes `Ethraffle_v4b` has a no-arg constructor (or implicit constructor).
contract Target is Ethraffle_v4b {
    constructor() Ethraffle_v4b() {}
}
