/*
 * @source: https://github.com/SmartContractSecurity/SWC-registry/blob/master/test_cases/dos_gas_limit/dos_simple.sol
 * @author: -
 * @vulnerable_at_lines: 17,18
 */


pragma solidity ^0.4.25;

contract DosOneFunc {

    address[] listAddresses;
    mapping(address => uint256) public pendingWithdrawals;

    function ifillArray() public returns (bool){
        if(listAddresses.length<1500) {
            // <yes> <report> DENIAL_OF_SERVICE
            require(pendingWithdrawals[msg.sender] + 350 >= pendingWithdrawals[msg.sender]);
            pendingWithdrawals[msg.sender] += 350;
            return true;

        } else {
            return false;
        }
    }

    function withdraw() public returns (bool) {
        uint256 amount = pendingWithdrawals[msg.sender];
        require(amount > 0);
        pendingWithdrawals[msg.sender] = 0;
        msg.sender.transfer(amount);
        return true;
    }
}