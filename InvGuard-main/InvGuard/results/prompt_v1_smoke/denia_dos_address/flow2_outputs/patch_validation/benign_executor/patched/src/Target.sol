/*
 * @source: https://github.com/SmartContractSecurity/SWC-registry/blob/master/test_cases/dos_gas_limit/dos_address.sol
 * @author: -
 * @vulnerable_at_lines: 16,17,18
 */

pragma solidity ^0.4.25;

contract DosGas {

    address[] creditorAddresses;
    mapping(address => uint) public balances;
    bool win = false;

    function emptyCreditors() public {
        require(msg.sender == address(this));
        if(creditorAddresses.length > 1500) {
            for (uint i = 0; i < creditorAddresses.length; i++) {
                balances[creditorAddresses[i]] += 1 ether; // Example amount
            }
            creditorAddresses = new address[](0);
            win = true;
        }
    }

    function addCreditors() public returns (bool) {
        for(uint i = 0; i < 350; i++) {
            creditorAddresses.push(msg.sender);
        }
        return true;
    }

    function withdraw() public {
        uint amount = balances[msg.sender];
        require(amount > 0, "No funds to withdraw");
        balances[msg.sender] = 0;
        msg.sender.transfer(amount);
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
