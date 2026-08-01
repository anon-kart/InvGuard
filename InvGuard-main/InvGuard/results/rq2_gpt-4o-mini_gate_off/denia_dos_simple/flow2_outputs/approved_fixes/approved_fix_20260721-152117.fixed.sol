/*
 * @source: https://github.com/SmartContractSecurity/SWC-registry/blob/master/test_cases/dos_gas_limit/dos_simple.sol
 * @author: -
 * @vulnerable_at_lines: 17,18
 */


pragma solidity ^0.4.25;

contract DosOneFunc {

    mapping(address => uint) public balances;

    function ifillArray() public returns (bool){
        require(msg.sender == tx.origin); // Access control

        // Instead of pushing to an array, we just record the balance
        balances[msg.sender] += 350; // Record amount owed
        return true;
    }

    function withdraw() public {
        uint amount = balances[msg.sender];
        require(amount > 0, "No funds to withdraw");
        balances[msg.sender] = 0; // Update state before external call
        msg.sender.transfer(amount); // Send funds
    }
}