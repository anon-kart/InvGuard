/*
 * @source: https://github.com/SmartContractSecurity/SWC-registry/blob/master/test_cases/dos_gas_limit/dos_address.sol
 * @author: -
 * @vulnerable_at_lines: 16,17,18
 */

pragma solidity ^0.4.25;

contract DosGas {

    address[] creditorAddresses;
    bool win = false;
    mapping(address => uint) public pendingWithdrawals;
    bool private _locked;

    function emptyCreditors() public {
        require(!_locked);
        _locked = true;
        // convert to a pull-payment pattern: record amounts owed instead of pushing payments
        if(creditorAddresses.length>1500) {
            for (uint i = 0; i < creditorAddresses.length; i++) {
                address creditor = creditorAddresses[i];
                // increment owed amount by 1 per occurrence (prevent overflow check)
                uint newAmount = pendingWithdrawals[creditor] + 1;
                require(newAmount >= pendingWithdrawals[creditor]);
                pendingWithdrawals[creditor] = newAmount;
            }
            creditorAddresses = new address[](0);
            win = true;
        }
        _locked = false;
    }

    function withdraw() public {
        require(!_locked);
        _locked = true;
        uint amount = pendingWithdrawals[msg.sender];
        require(amount > 0);
        // move state update before external call
        pendingWithdrawals[msg.sender] = 0;
        // ensure failures propagate
        require(msg.sender.send(amount));
        _locked = false;
    }

    function addCreditors() public returns (bool) {
        for(uint i=0;i<350;i++) {
          creditorAddresses.push(msg.sender);
        }
        return true;
    }

    function iWin() public view returns (bool) {
        return win;
    }

    function numberCreditors() public view returns (uint) {
        return creditorAddresses.length;
    }
}


// ---- auto-added by BenignExecutor ----
// Provides a stable deployable name used by the harness: `Target`.
// Assumes `DosGas` has a no-arg constructor (or implicit constructor).
contract Target is DosGas {
    constructor() DosGas() {}
}
