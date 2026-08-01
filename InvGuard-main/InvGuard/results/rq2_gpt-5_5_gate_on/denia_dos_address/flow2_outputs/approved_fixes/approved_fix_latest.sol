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

    function emptyCreditors() public {
        // <yes> <report> DENIAL_OF_SERVICE
        if(creditorAddresses.length>1500) {
            creditorAddresses = new address[](0);
            win = true;
        }
    }

    function withdraw() public {
        uint amount = pendingWithdrawals[msg.sender];
        require(amount > 0);
        pendingWithdrawals[msg.sender] = 0;
        msg.sender.transfer(amount);
    }

    function addCreditors() public returns (bool) {
        require(pendingWithdrawals[msg.sender] + 350 ether >= pendingWithdrawals[msg.sender]);
        pendingWithdrawals[msg.sender] += 350 ether;
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
