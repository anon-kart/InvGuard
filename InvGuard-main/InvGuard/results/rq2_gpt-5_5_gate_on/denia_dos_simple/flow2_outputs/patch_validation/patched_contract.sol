/*
 * @source: https://github.com/SmartContractSecurity/SWC-registry/blob/master/test_cases/dos_gas_limit/dos_simple.sol
 * @author: -
 * @vulnerable_at_lines: 17,18
 */


pragma solidity ^0.4.25;

contract DosOneFunc {

    address[] listAddresses;
    mapping(address => uint256) public pendingPayments;

    function ifillArray() public returns (bool){
        require(pendingPayments[msg.sender] + 350 >= pendingPayments[msg.sender]);
        pendingPayments[msg.sender] += 350;
        return true;
    }

    function withdrawPayments() public returns (bool) {
        uint256 amount = pendingPayments[msg.sender];
        require(amount > 0);
        pendingPayments[msg.sender] = 0;
        msg.sender.transfer(amount);
        return true;
    }
}