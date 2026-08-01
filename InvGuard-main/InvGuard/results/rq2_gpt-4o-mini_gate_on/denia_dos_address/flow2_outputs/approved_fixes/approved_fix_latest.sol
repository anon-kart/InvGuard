/*
 * @source: https://github.com/SmartContractSecurity/SWC-registry/blob/master/test_cases/dos_gas_limit/dos_address.sol
 * @author: -
 * @vulnerable_at_lines: 16,17,18
 */

pragma solidity ^0.4.25;

contract DosGas {

    mapping(address => uint) public balances;
    bool win = false;

    function emptyCreditors(address[] creditorAddresses) public {
        require(msg.sender == address(this)); // Access control
        require(creditorAddresses.length > 1500, "Not enough creditors");
        for (uint i = 0; i < creditorAddresses.length; i++) {
            balances[creditorAddresses[i]] += 1; // Record amounts owed
        }
        win = true;
    }

    function addCreditors() public returns (bool) {
        for(uint i = 0; i < 350; i++) {
            balances[msg.sender] += 1; // Record amounts owed directly
        }
        return true;
    }

    function iWin() public view returns (bool) {
        return win;
    }

    function withdraw() public {
        uint amount = balances[msg.sender];
        require(amount > 0, "No funds to withdraw");
        balances[msg.sender] = 0; // Update state before external call
        require(msg.sender.send(amount)); // Ensure transfer succeeds
    }
}