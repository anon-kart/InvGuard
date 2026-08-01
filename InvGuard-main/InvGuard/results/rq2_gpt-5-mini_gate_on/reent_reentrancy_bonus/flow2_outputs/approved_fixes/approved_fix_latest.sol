/*
 * @source: https://consensys.github.io/smart-contract-best-practices/known_attacks/
 * @author: consensys
 * @vulnerable_at_lines: 28
 */

pragma solidity ^0.4.24;

contract Reentrancy_bonus{

    // INSECURE
    mapping (address => uint) private userBalances;
    mapping (address => bool) private claimedBonus;
    mapping (address => uint) private rewardsForA;
    bool private _locked;

    function withdrawReward(address recipient) public {
        uint amountToWithdraw = rewardsForA[recipient];
        rewardsForA[recipient] = 0;
        (bool success, ) = recipient.call.value(amountToWithdraw)("");
        require(success);
    }

    function getFirstWithdrawalBonus(address recipient) public {
        require(!_locked);
        require(!claimedBonus[recipient]); // Each recipient should only be able to claim the bonus once
        _locked = true;
        // Effects
        claimedBonus[recipient] = true;
        rewardsForA[recipient] += 100;
        // Interaction
        withdrawReward(recipient); // external call happens after state updates
        _locked = false;
    }
}
