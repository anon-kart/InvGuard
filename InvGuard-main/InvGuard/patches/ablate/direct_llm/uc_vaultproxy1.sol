/*
 * @source: etherscan.io 
 * @author: -
 * @vulnerable_at_lines: 14
 */

pragma solidity ^0.4.23;

contract Proxy  {
    modifier onlyOwner { if (msg.sender == Owner) _; } address Owner = msg.sender;
    function transferOwner(address _owner) public onlyOwner { Owner = _owner; } 
    function proxy(address target, bytes data) public payable {
        // <yes> <report> UNCHECKED_LL_CALLS
        target.call.value(msg.value)(data);
    }
}

contract VaultProxy is Proxy {
    address public Owner;
    mapping (address => uint256) public Deposits;

    function () public payable { }
    
    function Vault() public payable {
        if (msg.sender == tx.origin) {
            Owner = msg.sender;
            deposit();
        }
    }
    
    function deposit() public payable {
        if (msg.value > 0.25 ether) {
            Deposits[msg.sender] += msg.value;
        }
    }
    
    function withdraw(uint256 amount) public onlyOwner {
        require(amount > 0 && Deposits[msg.sender] >= amount);
        Deposits[msg.sender] -= amount; // Update state before external call
        (bool ok,) = msg.sender.call.value(amount)("");
        require(ok); // Require success of the call
    }
}