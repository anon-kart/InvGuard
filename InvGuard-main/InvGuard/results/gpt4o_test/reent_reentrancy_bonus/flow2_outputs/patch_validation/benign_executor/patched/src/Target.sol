pragma solidity ^0.4.24;

contract Reentrancy_bonus{

    mapping (address => uint) private userBalances;
    mapping (address => bool) private claimedBonus;
    mapping (address => uint) private rewardsForA;

    function withdrawReward(address recipient) public {
        uint amountToWithdraw = rewardsForA[recipient];
        rewardsForA[recipient] = 0;
        (bool success, ) = recipient.call.value(amountToWithdraw)("");
        require(success);
    }

    function getFirstWithdrawalBonus(address recipient) public {
        require(!claimedBonus[recipient]); // Each recipient should only be able to claim the bonus once
        rewardsForA[recipient] += 100;
        claimedBonus[recipient] = true;
        withdrawReward(recipient); // At this point, the caller will be able to execute getFirstWithdrawalBonus again.
    }
}


// ---- auto-added by BenignExecutor ----
// Provides a stable deployable name used by the harness: `Target`.
// Assumes `Reentrancy_bonus` has a no-arg constructor (or implicit constructor).
contract Target is Reentrancy_bonus {
    constructor() Reentrancy_bonus() {}
}
