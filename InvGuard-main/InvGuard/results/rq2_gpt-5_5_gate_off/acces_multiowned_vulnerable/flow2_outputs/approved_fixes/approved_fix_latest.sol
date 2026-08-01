/*
 * @source: https://github.com/SmartContractSecurity/SWC-registry/blob/master/test_cases/solidity/unprotected_critical_functions/multiowned_vulnerable/multiowned_vulnerable.sol
 * @author: -
 * @vulnerable_at_lines: 38
 */

pragma solidity ^0.4.23;

/**
 * @title MultiOwnable
 */
contract MultiOwnable {
  address public root;
  mapping (address => address) public owners; // owner => parent of owner

  /**
  * @dev The Ownable constructor sets the original `owner` of the contract to the sender
  * account.
  */
  constructor() public {
    root = msg.sender;
    owners[root] = root;
  }

  /**
  * @dev Throws if called by any account other than an owner.
  */
  modifier onlyOwner() {
    require(owners[msg.sender] != 0);
    _;
  }

  /**
  * @dev Adding new owners. Only an existing owner may add another owner.
  */
  function newOwner(address _owner) external onlyOwner returns (bool) {
    require(_owner != address(0));
    owners[_owner] = msg.sender;
    return true;
  }

  /**
    * @dev Deleting owners
    */
  function deleteOwner(address _owner) onlyOwner external returns (bool) {
    require(owners[_owner] == msg.sender || (owners[_owner] != 0 && msg.sender == root));
    owners[_owner] = address(0);
    return true;
  }
}

contract TestContract is MultiOwnable {

  function withdrawAll() onlyOwner public {
    require(msg.sender == root);
    msg.sender.transfer(this.balance);
  }

  function() payable public {
  }

}