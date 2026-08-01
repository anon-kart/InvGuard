/*
 * @source: https://github.com/SmartContractSecurity/SWC-registry/blob/master/test_cases/dos_gas_limit/dos_simple.sol
 * @author: -
 * @vulnerable_at_lines: 17,18
 */


pragma solidity ^0.4.25;

contract DosOneFunc {

    address[] listAddresses;
    mapping(address => uint) public balances;

    function ifillArray() public returns (bool){
        require(listAddresses.length < 1500, "Array limit reached");
        
        for(uint i = 0; i < 350; i++) {
            balances[msg.sender]++;
        }
        
        return true;
    }

    function withdraw() public {
        uint amount = balances[msg.sender];
        require(amount > 0, "No funds to withdraw");
        balances[msg.sender] = 0;
        msg.sender.transfer(amount);
    }
}