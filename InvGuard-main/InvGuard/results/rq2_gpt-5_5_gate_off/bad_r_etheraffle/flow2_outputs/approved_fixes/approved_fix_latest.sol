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
    bytes32 public randomnessCommitment;
    uint private revealedRandomness;
    bool private randomnessReady;
    uint private randomnessRaffleId;

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

    function commitRandomness(bytes32 _commitment) public {
        if (msg.sender == feeAddress && nextTicket < totalTickets) {
            randomnessCommitment = _commitment;
            randomnessRaffleId = raffleId;
            revealedRandomness = 0;
            randomnessReady = false;
        }
    }

    function revealRandomness(uint _randomness) public {
        if (msg.sender == feeAddress && nextTicket == totalTickets && randomnessRaffleId == raffleId && randomnessCommitment == keccak256(_randomness)) {
            revealedRandomness = _randomness;
            randomnessReady = true;
            chooseWinner();
        }
    }

    function chooseWinner() private {
        if (!randomnessReady || randomnessRaffleId != raffleId || randomnessCommitment != keccak256(revealedRandomness)) {
            return;
        }

        address seed1 = feeAddress;
        address seed2 = address(this);
        uint seed3 = revealedRandomness;
        bytes32 randHash = keccak256(revealedRandomness, randomnessCommitment, raffleId, address(this));

        uint winningNumber = uint(randHash) % totalTickets;
        address winningAddress = contestants[winningNumber].addr;
        RaffleResult(raffleId, winningNumber, winningAddress, seed1, seed2, seed3, randHash);

        // Start next raffle
        raffleId++;
        nextTicket = 0;
        blockNumber = raffleId;
        randomnessCommitment = 0;
        revealedRandomness = 0;
        randomnessReady = false;
        randomnessRaffleId = 0;

        // gaps.length = 0 isn't necessary here,
        // because buyTickets() eventually clears
        // the gaps array in the loop itself.

        // Distribute prize and fee
        winningAddress.transfer(prize);
        feeAddress.transfer(fee);
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